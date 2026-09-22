"""Language classification of a piece of text."""

from enum import StrEnum


class Language(StrEnum):
    """Script-level language classification produced by the normalizer.

    A ``StrEnum`` so it compares and serialises as the plain tag ("fa", "en",
    ...) that the database and JSON payloads already use, while still rejecting
    values outside the closed set.
    """

    PERSIAN = "fa"
    ENGLISH = "en"
    MIXED = "mixed"
    OTHER = "other"
    UNKNOWN = "unknown"

    @classmethod
    def coerce(cls, value: "str | Language | None") -> "Language":
        """Maps an arbitrary tag onto the closed set, defaulting to UNKNOWN."""
        if isinstance(value, cls):
            return value
        if not value:
            return cls.UNKNOWN
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.UNKNOWN
