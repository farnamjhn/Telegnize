#!/usr/bin/env python3
"""Exports labelled decisions from telegnize.sqlite into training JSONL for Laya."""

import argparse
import contextlib
import json
import random
import sqlite3
from pathlib import Path

from application.decision_questions import ASSESSMENT_QUESTIONS
from infrastructure.decision_engine.laya_engine import _to_laya_schema

DEFAULT_DB = "telegnize.sqlite"
DEFAULT_OUT_DIR = "data"


def export_decisions(
    db_path: str = DEFAULT_DB,
    output_dir: str = DEFAULT_OUT_DIR,
    val_split: float = 0.2,
    seed: int = 42,
) -> tuple[int, int]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Question schemas from Telegnize
    schemas = {q.key: _to_laya_schema(q) for q in ASSESSMENT_QUESTIONS}

    query = """
        SELECT
            m.id as message_id,
            m.sender_name,
            COALESCE(NULLIF(m.normalized_text, ''), m.text_content) as text,
            d.question_key,
            d.result_value
        FROM decisions d
        JOIN messages m ON d.target_id = m.id
        WHERE d.target_type = 'message'
        ORDER BY m.id
    """
    cursor.execute(query)
    rows = cursor.fetchall()

    grouped: dict[int, dict] = {}
    for row in rows:
        mid = row["message_id"]
        if mid not in grouped:
            grouped[mid] = {
                "state": {"sender": row["sender_name"], "text": row["text"]},
                "labels": {},
            }
        val = row["result_value"]
        with contextlib.suppress(Exception):
            val = json.loads(val)
        grouped[mid]["labels"][row["question_key"]] = val

    # Keep only messages that have all 6 core questions
    records = []
    for mid, item in grouped.items():
        labels = item["labels"]
        if len(labels) < 6:
            continue
        questions_dict = {}
        for qkey, qschema in schemas.items():
            if qkey not in labels:
                continue
            lbl = labels[qkey]
            # Convert score float into level index (0, 1, 2, 3)
            if qschema["type"] == "score" and isinstance(lbl, (int, float)):
                lbl = max(0, min(3, round(float(lbl))))
            questions_dict[qkey] = {**qschema, "label": lbl}

        records.append(
            {
                "id": mid,
                "state": item["state"],
                "questions": questions_dict,
            }
        )

    random.seed(seed)
    random.shuffle(records)

    n_val = int(len(records) * val_split)
    val_records = records[:n_val]
    train_records = records[n_val:]

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    train_file = out_path / "train.jsonl"
    val_file = out_path / "val.jsonl"

    with open(train_file, "w", encoding="utf-8") as f:
        for r in train_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(val_file, "w", encoding="utf-8") as f:
        for r in val_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Exported {len(records)} total examples:")
    print(f"  Train: {len(train_records)} -> {train_file}")
    print(f"  Val  : {len(val_records)} -> {val_file}")
    return len(train_records), len(val_records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export Telegnize decisions to training data."
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument(
        "--out", default=DEFAULT_OUT_DIR, help="Output directory for jsonl"
    )
    parser.add_argument(
        "--val-split", type=float, default=0.2, help="Validation fraction (0-1)"
    )
    args = parser.parse_args()
    export_decisions(db_path=args.db, output_dir=args.out, val_split=args.val_split)
