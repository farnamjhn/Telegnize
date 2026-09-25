#!/usr/bin/env python3
"""Fine-tune Laya on domain-specific decision questions.

Supports:
  1. Head-only training (fast, adapts decision heads in minutes on CPU/Mac MPS).
  2. Full fine-tuning (backbone encoder + decision heads).
  3. Automatic temperature calibration fitting on validation data.
  4. Exports standard Laya checkpoint (model.safetensors, config, tokenizer).

Usage:
    uv run python scripts/finetune_laya.py \
        --data data/train.jsonl --val-data data/val.jsonl
"""

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F
from laya.agent import Agent
from laya.common import (
    QTYPES,
    build_sequence,
    clamp_temperature,
    collate_items,
    render_options,
)
from safetensors.torch import save_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("finetune_laya")


def resolve_label_idx(q_internal: dict, raw_label: Any) -> int | None:
    """Map raw label value (e.g. 'positive', True, 2) to integer option index."""
    t = q_internal["t"]
    if t == "noul":
        # Options are [false, true]
        return 1 if bool(raw_label) else 0

    if t == "choice":
        keys = list(q_internal["crit"].keys())
        if raw_label in keys:
            return keys.index(raw_label)
        if isinstance(raw_label, int) and 0 <= raw_label < len(keys):
            return raw_label
        return None

    if t == "score":
        try:
            val = round(float(raw_label))
            k = len(q_internal["crit"])
            return max(0, min(k - 1, val))
        except (ValueError, TypeError):
            return None

    return None


def load_dataset(jsonl_path: str, agent: Agent) -> list[dict]:
    """Parse JSONL into flattened question items ready for collate_items."""
    tok = agent.tok
    max_len = agent.cfg.get("max_len", 512)
    head_max_len = agent.cfg.get("head_max_len", 192)

    items = []
    skipped = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for _line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            state = record["state"]
            questions = record.get("questions", {})

            for qid, qdef in questions.items():
                if "label" not in qdef:
                    continue
                q_internal = agent._to_internal(qdef)
                lbl_idx = resolve_label_idx(q_internal, qdef["label"])
                if lbl_idx is None:
                    skipped += 1
                    continue

                try:
                    seq, markers = build_sequence(
                        tok, state, q_internal, max_len, head_max_len
                    )
                    if len(markers) != len(render_options(q_internal)):
                        skipped += 1
                        continue
                    items.append(
                        {
                            "ids": seq,
                            "markers": markers,
                            "qtype": QTYPES[q_internal["t"]],
                            "label": lbl_idx,
                            "qid": qid,
                        }
                    )
                except Exception:
                    skipped += 1
                    continue

    logger.info(
        "Loaded %d question items from %s (skipped %d invalid).",
        len(items),
        jsonl_path,
        skipped,
    )
    return items


def make_batches(items: list[dict], batch_size: int, pad_token_id: int):
    """Yield batched tensor dictionaries using collate_items."""
    for i in range(0, len(items), batch_size):
        chunk = items[i : i + batch_size]
        batch = collate_items([chunk], pad_token_id)
        if batch is not None:
            yield batch


def evaluate(
    model, items: list[dict], device: torch.device, pad_id: int, batch_size: int = 16
):
    """Run model over items.

    Returns:
        avg loss, overall accuracy, and raw (logits, labels, qtypes).
    """
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    all_logits = []
    all_labels = []
    all_qtypes = []

    with torch.no_grad():
        for b in make_batches(items, batch_size, pad_id):
            logits, _ = model(
                b["input_ids"].to(device),
                b["attention_mask"].to(device),
                b["marker_pos"].to(device),
                b["marker_mask"].to(device),
                b["qtype"].to(device),
            )
            labels = b["label"].to(device)
            loss = F.cross_entropy(logits, labels)
            total_loss += loss.item() * len(labels)
            preds = logits.argmax(dim=-1)
            correct += (preds == labels).sum().item()
            total += len(labels)

            all_logits.append(logits.cpu())
            all_labels.append(labels.cpu())
            all_qtypes.append(b["qtype"].cpu())

    avg_loss = total_loss / max(1, total)
    acc = correct / max(1, total)
    logits_cat = torch.cat(all_logits, dim=0) if all_logits else torch.empty(0)
    labels_cat = torch.cat(all_labels, dim=0) if all_labels else torch.empty(0)
    qtypes_cat = torch.cat(all_qtypes, dim=0) if all_qtypes else torch.empty(0)

    return avg_loss, acc, logits_cat, labels_cat, qtypes_cat


def fit_temperature(
    logits: torch.Tensor, labels: torch.Tensor, qtypes: torch.Tensor
) -> list[float]:
    """Fit one temperature per question type (choice, score, noul) via grid search."""
    temps = [1.0, 1.0, 1.0]
    candidates = np.linspace(0.5, 3.5, 61)

    for qt_name, qt_idx in QTYPES.items():
        mask = qtypes == qt_idx
        if not mask.any():
            continue
        sub_logits = logits[mask]
        sub_labels = labels[mask]

        best_t = 1.0
        best_nll = float("inf")

        for t in candidates:
            scaled = sub_logits / t
            nll = F.cross_entropy(scaled, sub_labels).item()
            if nll < best_nll:
                best_nll = nll
                best_t = float(t)

        temps[qt_idx] = clamp_temperature(best_t)
        logger.info(
            "Fitted temperature for %s: %.3f (NLL: %.4f)",
            qt_name,
            temps[qt_idx],
            best_nll,
        )

    return temps


def train(
    base_model: str,
    train_data: str,
    val_data: str,
    output_dir: str,
    subfolder: str | None = None,
    epochs: int = 3,
    batch_size: int = 8,
    lr: float = 2e-4,
    mode: str = "head-only",
    device_name: str | None = None,
):
    start_time = time.time()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if base_model in (
        "multilingual",
        "laya-multilingual",
        "multi",
        "convaiinnovations/laya-multilingual",
    ):
        base_model = "convaiinnovations/laya"
        subfolder = "multilingual"

    # 1. Device resolution
    if device_name:
        device = torch.device(device_name)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    logger.info(
        "Initializing Laya agent (base: %s, subfolder: %s) on device: %s",
        base_model,
        subfolder,
        device,
    )
    agent = Agent(base_model, subfolder=subfolder, device=str(device))
    model = agent.model
    tok = agent.tok
    cfg = dict(agent.cfg)

    # 2. Freeze / unfreeze
    if mode == "head-only":
        logger.info("Training mode: HEAD-ONLY. Freezing encoder backbone.")
        for p in model.encoder.parameters():
            p.requires_grad = False
        trainable = [p for p in model.parameters() if p.requires_grad]
    else:
        logger.info("Training mode: FULL. Training encoder and heads.")
        for p in model.parameters():
            p.requires_grad = True
        trainable = list(model.parameters())

    trainable_params = sum(p.numel() for p in trainable)
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(
        "Trainable parameters: %d / %d (%.2f%%)",
        trainable_params,
        total_params,
        100 * trainable_params / total_params,
    )

    # 3. Load datasets
    train_items = load_dataset(train_data, agent)
    val_items = load_dataset(val_data, agent) if val_data else []

    if not train_items:
        raise ValueError(f"No valid training items found in {train_data}")

    optimizer = torch.optim.AdamW(trainable, lr=lr, weight_decay=0.01)

    # Initial eval
    if val_items:
        init_loss, init_acc, _, _, _ = evaluate(
            model, val_items, device, tok.pad_token_id
        )
        logger.info(
            "Pre-training Validation: Loss=%.4f, Accuracy=%.2f%%",
            init_loss,
            init_acc * 100,
        )

    # 4. Training loop
    logger.info("Starting training for %d epochs...", epochs)
    for epoch in range(1, epochs + 1):
        model.train()
        np.random.shuffle(train_items)
        epoch_loss = 0.0
        n_batches = 0

        for b in make_batches(train_items, batch_size, tok.pad_token_id):
            optimizer.zero_grad()
            logits, _ = model(
                b["input_ids"].to(device),
                b["attention_mask"].to(device),
                b["marker_pos"].to(device),
                b["marker_mask"].to(device),
                b["qtype"].to(device),
            )
            labels = b["label"].to(device)
            loss = F.cross_entropy(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(trainable, max_norm=1.0)
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        avg_train_loss = epoch_loss / max(1, n_batches)
        if val_items:
            val_loss, val_acc, _, _, _ = evaluate(
                model, val_items, device, tok.pad_token_id
            )
            logger.info(
                "Epoch %d/%d - Train Loss: %.4f | Val Loss: %.4f | Val Acc: %.2f%%",
                epoch,
                epochs,
                avg_train_loss,
                val_loss,
                val_acc * 100,
            )
        else:
            logger.info("Epoch %d/%d - Train Loss: %.4f", epoch, epochs, avg_train_loss)

    # 5. Final Evaluation & Temperature Calibration
    fitted_temps = [1.0, 1.0, 1.0]
    if val_items:
        val_loss, val_acc, val_logits, val_labels, val_qtypes = evaluate(
            model, val_items, device, tok.pad_token_id
        )
        logger.info(
            "Final Validation: Loss=%.4f, Accuracy=%.2f%%", val_loss, val_acc * 100
        )
        fitted_temps = fit_temperature(val_logits, val_labels, val_qtypes)

    # 6. Save checkpoint
    logger.info("Saving fine-tuned checkpoint to %s...", out_dir)
    # Weights
    weights_path = out_dir / "model.safetensors"
    save_file(model.state_dict(), weights_path)

    # Config
    cfg["temperature"] = fitted_temps
    cfg["temperature_by_options"] = {}  # remove old buckets so fitted temps take effect
    cfg["training"] = {
        "fine_tuned_from_checkpoint": True,
        "base_model": base_model,
        "epochs": epochs,
        "mode": mode,
        "train_samples": len(train_items),
        "duration_seconds": round(time.time() - start_time, 2),
    }
    with open(out_dir / "rl_agent_config.json", "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    # Tokenizer
    tok_dir = out_dir / "tokenizer"
    tok.save_pretrained(tok_dir)

    logger.info("Fine-tuning complete! Model saved to %s", out_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune Laya decision models.")
    parser.add_argument(
        "--base", default="convaiinnovations/laya", help="Base model ID or path"
    )
    parser.add_argument(
        "--subfolder", default=None, help="Subfolder in base repo (e.g. multilingual)"
    )
    parser.add_argument(
        "--data", default="data/train.jsonl", help="Training JSONL dataset"
    )
    parser.add_argument(
        "--val-data", default="data/val.jsonl", help="Validation JSONL dataset"
    )
    parser.add_argument(
        "--output-dir",
        default="checkpoints/laya-multilingual-telegnize",
        help="Directory to save checkpoint",
    )
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument(
        "--mode", choices=["head-only", "full"], default="head-only", help="Training mode"
    )
    parser.add_argument("--device", default=None, help="Device (cpu, mps, cuda)")
    args = parser.parse_args()

    train(
        base_model=args.base,
        train_data=args.data,
        val_data=args.val_data,
        output_dir=args.output_dir,
        subfolder=args.subfolder,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        mode=args.mode,
        device_name=args.device,
    )
