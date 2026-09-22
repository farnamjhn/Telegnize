"""Word lists that give message text behavioural meaning.

These live in the domain layer because they define what Telegnize *means* by a
cold closure or an expression of affection, not how any adapter works.

## What these are and are not

Each set is a **marker list**: tokens whose presence is worth counting. A count
is an observation about wording, not a measurement of a feeling. "I love that
restaurant" counts as an affection marker; a long, warm message with no listed
word counts as none. Read the counts as a rough texture of how someone writes,
compare them between participants in the same conversation, and do not read
them as a score of the relationship.

Matching is token-level against normalized text, so multi-word expressions
(``دوستت دارم``, "thank you") are caught by their distinctive token rather than
as a phrase, and contractions are matched on the stem the tokenizer leaves
behind ("I'll" tokenizes to "i" and "ll").

Persian entries use the forms hazm's normalizer produces. Some Persian words
carry more than one function — ``قربونت`` is both an endearment and a way of
saying thanks — and are listed under the sense they most often carry in
conversation.
"""

#: Replies that close a turn without investing in it. Matched against the whole
#: message, so "ok" counts and "ok but what about tuesday" does not.
LOW_INVESTMENT_TOKENS: frozenset[str] = frozenset(
    {
        "k", "ok", "kk", "cool", "yeah", "yup", "lol", "nice",
        "fine", "sure", "alright", "nm", "idk", "thx", "ty", "np",
        "اوکی", "اوک", "باشه", "مرسی", "ممنون", "خب", "اره", "آره", "نه", "نوچ",
    }
)

#: Terms of endearment and expressions of closeness or longing.
AFFECTION_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "love", "loved", "loves", "loving", "miss", "missed", "missing",
        "babe", "baby", "honey", "darling", "sweetheart", "sweetie", "dear",
        "hug", "hugs", "kiss", "kisses", "xoxo", "cutie", "beautiful",
        # Persian
        "عشق", "عشقم", "عزیزم", "عزیز", "جانم", "جونم", "نفسم", "زندگیم",
        "قربونت", "قربانت", "فدات", "فدایت", "دلم", "دلتنگ", "دوستت",
        "بوس", "بوسه", "ماچ", "بغل", "گلم", "خوشگلم", "جیگرم", "نازم",
    }
)

#: Repair moves: admitting fault or asking to be excused.
APOLOGY_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "sorry", "apologize", "apologise", "apologies", "apology",
        "forgive", "regret", "fault",
        # Persian
        "ببخشید", "ببخش", "معذرت", "شرمنده", "عذر", "عذرخواهی",
        "متاسفم", "متأسفم",
    }
)

#: Acknowledgement of something the other person did.
GRATITUDE_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "thanks", "thank", "thx", "ty", "grateful", "gratitude",
        "appreciate", "appreciated", "appreciation",
        # Persian. These also appear in LOW_INVESTMENT_TOKENS, where they are
        # matched as a whole message; here they are matched anywhere in one.
        "مرسی", "ممنون", "ممنونم", "متشکرم", "تشکر", "سپاس", "سپاسگزارم",
    }
)

#: First-person singular reference. A high rate relative to the collective set
#: is the self-focus marker that shows up across text-psychology research.
SELF_REFERENCE_TOKENS: frozenset[str] = frozenset(
    {
        # English. Contractions are matched on the stem the tokenizer leaves,
        # so "i'm" and "i've" both arrive as "i"; the spelled-out forms people
        # type without an apostrophe are listed separately.
        "i", "me", "my", "mine", "myself", "im", "ive",
        # Persian
        "من", "منو", "منم", "خودم", "بهم", "برام", "واسم", "باهام", "ازم",
    }
)

#: First-person plural reference: the participants spoken of as a unit.
COLLECTIVE_REFERENCE_TOKENS: frozenset[str] = frozenset(
    {
        # English. "we're" and "we've" arrive as "we"; "were" is left out
        # because it is far more often the past tense of "be".
        "we", "us", "our", "ours", "ourselves", "weve",
        # Persian
        "ما", "مارو", "خودمون", "بهمون", "برامون", "واسمون", "باهامون",
        "ازمون", "باهم", "دوتامون",
    }
)
