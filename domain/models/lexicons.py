"""Linguistic constants used by domain entities.

Kept in the domain layer because they encode behavioural meaning (what counts
as a low-investment reply), not an implementation detail of any adapter.
"""

# Replies that close a turn without investing in it, in English and Persian.
LOW_INVESTMENT_TOKENS: frozenset[str] = frozenset(
    {
        "k", "ok", "kk", "cool", "yeah", "yup", "lol", "nice",
        "fine", "sure", "alright", "nm", "idk", "thx", "ty", "np",
        "اوکی", "اوک", "باشه", "مرسی", "ممنون", "خب", "اره", "آره", "نه", "نوچ",
    }
)
