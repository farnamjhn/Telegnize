"""Vocabulary and style matching, computed in one pass over a chat's text.

Everything else in analytics is an aggregate query. These two figures cannot
be: both are about *which* words were used, and SQLite has no tokenizer. So
they stream the chat instead — one row in memory at a time, one pass, no
buffering of the whole conversation.

Both are reported as comparisons between the people in one conversation.
Neither is meaningful on its own: lexical diversity depends on the language
being written and on how much of it there is, and style matching describes a
pair, not a person.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from itertools import pairwise

from domain.models.lexicons import FUNCTION_WORD_CATEGORIES
from domain.models.message import tokenize

#: Tokens in the window a moving-average type-token ratio is taken over.
#:
#: Raw TTR falls as a sample grows — a thousand words cannot help repeating
#: more than ten do — so comparing two people who wrote different amounts by
#: raw TTR measures how much they wrote. MATTR takes the ratio over a fixed
#: window and averages it, which removes that dependence. 500 is the usual
#: choice and is small enough that a participant in a short chat still gets a
#: figure.
MATTR_WINDOW = 500

#: Ireland & Pennebaker's constant, which keeps a category both people used
#: zero times from dividing by zero. It also means two zeroes score as a match,
#: which is the intended reading: neither of them reached for that category.
_LSM_EPSILON = 0.0001

_ROUNDING = 2


@dataclass(frozen=True)
class SenderVocabulary:
    """How varied one participant's wording is."""

    token_count: int = 0
    unique_count: int = 0
    type_token_ratio: float | None = None
    #: MATTR. ``None`` until there is anything to measure; equal to the plain
    #: ratio when the participant wrote less than one window, where it is not
    #: comparable with someone who wrote more.
    lexical_diversity: float | None = None


@dataclass(frozen=True)
class StyleMatching:
    """How closely two people's function-word use tracks, turn by turn."""

    lsm_percent: float | None = None
    by_category: dict[str, float] = field(default_factory=dict)
    turn_pairs: int = 0


@dataclass(frozen=True)
class LexicalProfile:
    by_sender: dict[str, SenderVocabulary] = field(default_factory=dict)
    style_matching: StyleMatching = StyleMatching()


def build_lexical_profile(
    rows: Iterable[tuple[str, str]],
    mattr_window: int = MATTR_WINDOW,
) -> LexicalProfile:
    """Reads a chat's messages in order and returns both figures.

    ``rows`` is (sender_id, text) chronologically. Consecutive messages from
    one sender are one turn, which is the unit style matching compares: a
    reply answers a turn, not each message in it.
    """
    tokens_by_sender: dict[str, list[str]] = {}
    turns: list[tuple[str, Counter]] = []

    current_sender: str | None = None
    current_turn: Counter = Counter()

    for sender_id, text in rows:
        tokens = tokenize(text)
        if sender_id != current_sender:
            if current_sender is not None and current_turn:
                turns.append((current_sender, current_turn))
            current_sender, current_turn = sender_id, Counter()
        if tokens:
            tokens_by_sender.setdefault(sender_id, []).extend(tokens)
            current_turn.update(tokens)
    if current_sender is not None and current_turn:
        turns.append((current_sender, current_turn))

    return LexicalProfile(
        by_sender={
            sender_id: _vocabulary(tokens, mattr_window)
            for sender_id, tokens in tokens_by_sender.items()
        },
        style_matching=_style_matching(turns),
    )


def _vocabulary(tokens: list[str], window: int) -> SenderVocabulary:
    total = len(tokens)
    if total == 0:
        return SenderVocabulary()
    unique = len(set(tokens))
    return SenderVocabulary(
        token_count=total,
        unique_count=unique,
        type_token_ratio=round(unique / total, 3),
        lexical_diversity=_mattr(tokens, min(window, total)),
    )


def _mattr(tokens: list[str], window: int) -> float | None:
    """Mean type-token ratio over every window of ``window`` consecutive tokens.

    Kept to one pass with a sliding count rather than rebuilding a set per
    position, which on a chat of any size is the difference between a query and
    a wait.
    """
    if window <= 0 or not tokens:
        return None
    if window >= len(tokens):
        return round(len(set(tokens)) / len(tokens), 3)

    counts: Counter = Counter(tokens[:window])
    running = len(counts)
    windows = 1
    for index in range(window, len(tokens)):
        leaving, arriving = tokens[index - window], tokens[index]
        counts[leaving] -= 1
        if counts[leaving] == 0:
            del counts[leaving]
        counts[arriving] += 1
        running += len(counts)
        windows += 1
    return round(running / windows / window, 3)


def _style_matching(turns: list[tuple[str, Counter]]) -> StyleMatching:
    """Averages category-wise LSM over every pair of adjacent turns.

    Only pairs where the speaker changes are counted: a burst continuing your
    own turn matches your own style by construction and would inflate this.
    """
    per_category: dict[str, list[float]] = {name: [] for name in FUNCTION_WORD_CATEGORIES}
    pair_scores: list[float] = []

    for (first_sender, first), (second_sender, second) in pairwise(turns):
        if first_sender == second_sender:
            continue
        first_total, second_total = sum(first.values()), sum(second.values())
        if not first_total or not second_total:
            continue

        scores = []
        for name, vocabulary in FUNCTION_WORD_CATEGORIES.items():
            first_rate = _share(first, vocabulary, first_total)
            second_rate = _share(second, vocabulary, second_total)
            score = 1.0 - abs(first_rate - second_rate) / (
                first_rate + second_rate + _LSM_EPSILON
            )
            per_category[name].append(score)
            scores.append(score)
        if scores:
            pair_scores.append(sum(scores) / len(scores))

    if not pair_scores:
        return StyleMatching()
    return StyleMatching(
        lsm_percent=round(sum(pair_scores) / len(pair_scores) * 100, _ROUNDING),
        by_category={
            name: round(sum(values) / len(values) * 100, _ROUNDING)
            for name, values in per_category.items()
            if values
        },
        turn_pairs=len(pair_scores),
    )


def _share(counts: Mapping[str, int], vocabulary: frozenset[str], total: int) -> float:
    return sum(count for token, count in counts.items() if token in vocabulary) / total
