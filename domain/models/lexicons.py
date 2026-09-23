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

#: Absolutist words: the vocabulary of no exceptions and no middle ground.
#:
#: The English list is the absolutist dictionary from Al-Mosaiwi & Johnstone's
#: work on absolutist thinking, kept whole rather than trimmed so the rate
#: stays comparable to published figures. It includes common words like "all"
#: and "must" by design; read the rate, and only against another participant in
#: the same conversation.
ABSOLUTIST_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "absolutely", "all", "always", "complete", "completely", "constant",
        "constantly", "definitely", "entire", "entirely", "ever", "every",
        "everyone", "everything", "full", "must", "never", "nothing",
        "totally", "whole",
        # Persian
        "همیشه", "هیچوقت", "هیچ‌وقت", "هرگز", "اصلا", "اصلاً", "قطعا", "قطعاً",
        "کاملا", "کاملاً", "مطلقا", "مطلقاً", "تماما", "تماماً", "همه",
        "هیچی", "هیچ", "حتما", "حتماً", "باید", "دائما", "همیشگی",
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

#: Tentative wording: saying something while leaving room to be wrong.
#:
#: Multi-word hedges are matched on their distinctive token, the way the rest
#: of this module matches: "I guess" on ``guess``, ``فکر کنم`` on ``فکر`` and its
#: colloquial spelling ``فک``. That makes ``فکر`` a hedge wherever it appears,
#: including "don't think about it" — the cost of token matching, and the
#: reason this is a rate to compare between participants rather than a count
#: that means anything on its own.
HEDGE_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "maybe", "perhaps", "probably", "possibly", "guess", "might",
        "suppose", "kinda", "kind", "sorta", "sort", "somewhat",
        "apparently", "seemingly", "presumably", "arguably", "ish",
        # Persian
        "شاید", "احتمالا", "احتمالاً", "احتمال", "ظاهرا", "ظاهراً",
        "انگار", "انگاری", "نظرم", "فکر", "فک", "گمونم", "گمان",
        "تقریبا", "تقریباً", "یجورایی", "نمیدونم", "نمی‌دونم",
    }
)

#: Short validations that keep a conversation moving without adding to it.
#:
#: Matched against the whole message, like :data:`LOW_INVESTMENT_TOKENS`, and
#: overlapping with it on purpose: the two ask different questions of the same
#: word. A cold closure is about ending a turn cheaply; a backchannel is about
#: signalling "still here, go on". ``باشه`` can do either, and is counted under
#: both.
BACKCHANNEL_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "ok", "okay", "k", "kk", "yeah", "yep", "yup", "yes", "sure",
        "alright", "right", "true", "exactly", "aha", "ah", "ahh", "oh",
        "i see", "gotcha", "mhm", "hmm", "cool", "nice", "same",
        # Persian
        "اره", "آره", "اوکی", "اوک", "باشه", "درسته", "دقیقا", "دقیقاً",
        "حتما", "حتماً", "اهان", "آهان", "اها", "آها", "خب", "خوبه",
        "ایول", "موافقم", "همینطوره", "بله",
    }
)

#: Words that mark a question even where the punctuation does not.
#:
#: Persian questions are routinely written without ``؟``, so counting only
#: question marks undercounts them badly — which is the whole reason this list
#: exists rather than a regex over punctuation.
QUESTION_WORD_TOKENS: frozenset[str] = frozenset(
    {
        # English
        "what", "why", "how", "when", "where", "who", "whom", "whose",
        "which", "whats", "hows", "wheres",
        # Persian
        "چرا", "چطور", "چطوری", "چگونه", "کی", "کِی", "کجا", "کجاست",
        "چیه", "چیست", "چی", "چه", "آیا", "ایا", "چند", "چقدر",
        "کدوم", "کدام", "مگه", "مگر", "هان",
    }
)

#: Function words by category, for Linguistic Style Matching.
#:
#: LSM compares how much of each person's writing is made of function words —
#: the grammatical scaffolding nobody chooses deliberately — rather than what
#: they are talking about. Ireland & Pennebaker's categories are reproduced
#: here in the two languages this corpus is written in. Persian is heavily
#: agglutinative and clitics attach to their host word, so the Persian members
#: are the free-standing forms the normalizer leaves behind; the category is
#: therefore undercounted in Persian relative to English, which is why LSM is
#: only ever compared between two people writing the same mix.
FUNCTION_WORD_CATEGORIES: dict[str, frozenset[str]] = {
    "personal_pronouns": frozenset(
        {
            "i", "me", "my", "mine", "myself", "im", "ive", "we", "us", "our",
            "ours", "you", "your", "yours", "he", "him", "his", "she", "her",
            "hers", "they", "them", "their", "theirs",
            "من", "منو", "منم", "ما", "مارو", "تو", "توئه", "شما", "او", "اون",
            "اونا", "آنها", "ایشون", "خودم", "خودت", "خودش", "خودمون",
        }
    ),
    "impersonal_pronouns": frozenset(
        {
            "it", "its", "this", "that", "these", "those", "something",
            "anything", "everything", "nothing", "one", "some", "which",
            "این", "اون", "آن", "اینا", "اونا", "همین", "همون", "چیزی",
            "هیچی", "یچیزی", "یه‌چیزی",
        }
    ),
    "articles": frozenset({"a", "an", "the", "یه", "یک"}),
    "prepositions": frozenset(
        {
            "in", "on", "at", "to", "for", "with", "from", "by", "about",
            "of", "into", "over", "under", "after", "before", "between",
            "در", "به", "از", "با", "برای", "تا", "روی", "زیر", "بین",
            "بعد", "قبل", "پیش", "سمت", "طرف", "واسه", "رو",
        }
    ),
    "auxiliary_verbs": frozenset(
        {
            "am", "is", "are", "was", "were", "be", "been", "being", "do",
            "does", "did", "have", "has", "had", "will", "would", "can",
            "could", "should", "shall", "may", "might", "must",
            "هست", "هستم", "هستی", "هستیم", "بود", "بودم", "بودی", "باشه",
            "باشد", "شد", "شده", "میشه", "می‌شه", "باید", "بشه", "داره",
            "دارم", "داری", "داشت", "کرد", "کنم", "کنی", "کنه",
        }
    ),
    "adverbs": frozenset(
        {
            "very", "really", "just", "so", "too", "also", "now", "then",
            "here", "there", "still", "already", "again", "always", "never",
            "خیلی", "واقعا", "واقعاً", "فقط", "هم", "الان", "حالا", "بعدش",
            "اینجا", "اونجا", "هنوز", "دیگه", "باز", "همیشه", "هیچوقت", "کلا",
        }
    ),
    "conjunctions": frozenset(
        {
            "and", "but", "or", "so", "because", "if", "when", "while",
            "although", "though", "than", "that", "as",
            "و", "ولی", "اما", "یا", "چون", "اگه", "اگر", "وقتی", "که",
            "پس", "هرچند", "بلکه", "تااینکه",
        }
    ),
    "negations": frozenset(
        {
            "no", "not", "never", "none", "nobody", "nothing", "nowhere",
            "cant", "dont", "didnt", "wont", "isnt", "arent", "wasnt",
            "نه", "نیست", "نیستم", "نداره", "ندارم", "نکن", "نمیشه",
            "نمی‌شه", "نمیدونم", "نمی‌دونم", "هیچ", "هیچی", "نخیر",
        }
    ),
    "quantifiers": frozenset(
        {
            "all", "some", "any", "many", "much", "more", "most", "few",
            "little", "lot", "lots", "every", "each", "both", "half",
            "همه", "بعضی", "خیلی", "چندتا", "چند", "کم", "زیاد", "بیشتر",
            "کمتر", "هرکدوم", "هردو", "نصف", "تعدادی",
        }
    ),
}
