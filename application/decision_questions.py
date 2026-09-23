"""The catalogue of questions Telegnize asks about conversations.

These are product decisions — what we want to know about a chat — so they live
in the application layer rather than next to the model that answers them.

``ASSESSMENT_QUESTIONS`` is the set run over every message of a chat to build a
relational assessment. Several of them name constructs from Gottman's
observational research on couples; a classifier reading chat text is a long way
from a coded lab observation, so the results are described here and in
``docs/analytics.md`` as what the classifier saw, never as a diagnosis.
"""

from collections.abc import Sequence

from application.ports.decision_engine import DecisionQuestion
from domain.models.analysis import DecisionType

MESSAGE_QUESTIONS: Sequence[DecisionQuestion] = (
    DecisionQuestion(
        key="tone",
        decision_type=DecisionType.CHOICE,
        instructions="What is the emotional tone of this message?",
        criteria={
            "affectionate": "warm, loving, caring, affectionate, romantic",
            "friendly": "friendly, supportive, happy, enthusiastic",
            "casual": "everyday, relaxed, informal chat",
            "frustrated": "annoyed, complaining, upset, sarcastic",
            "neutral": "factual, simple statement, informative, without strong emotion",
        },
    ),
    DecisionQuestion(
        key="is_conflict",
        decision_type=DecisionType.NOUL,
        instructions=(
            "Does this message express tension, argument, grievance, "
            "or interpersonal conflict?"
        ),
    ),
)

CONVERSATION_QUESTIONS: Sequence[DecisionQuestion] = (
    DecisionQuestion(
        key="relationship_dynamic",
        decision_type=DecisionType.CHOICE,
        instructions=(
            "What best characterizes the interpersonal dynamic between the "
            "participants in this conversation snippet?"
        ),
        criteria={
            "close_friends": "frequent banter, casual intimacy, shared humor, comfort",
            "romantic": "affectionate, loving, caring, intimate emotional sharing",
            "colleagues": "work or task-oriented, structured, professional, informative",
            "acquaintances": "polite, courteous, formal, low intimacy",
        },
    ),
    DecisionQuestion(
        key="overall_sentiment",
        decision_type=DecisionType.CHOICE,
        instructions="What is the overall sentiment of this conversation exchange?",
        criteria={
            "positive": "harmonious, warm, playful, supportive",
            "neutral": "matter-of-fact, transactional, informational",
            "tense": "strained, irritated, conflicting, distant",
        },
    ),
)


#: Asked of every message in an assessment pass.
ASSESSMENT_QUESTIONS: Sequence[DecisionQuestion] = (
    DecisionQuestion(
        key="valence",
        decision_type=DecisionType.CHOICE,
        instructions="What is the emotional valence of this message?",
        criteria={
            "positive": "warm, appreciative, affectionate, playful, encouraging",
            "neutral": "factual, logistical, informational, without charge",
            "negative": "cold, critical, hurt, angry, complaining, dismissive",
        },
    ),
    DecisionQuestion(
        key="is_bid",
        decision_type=DecisionType.NOUL,
        instructions=(
            "Is the sender reaching out to share a thought, feeling, joke, or "
            "image, or otherwise seeking the other person's engagement?"
        ),
    ),
    DecisionQuestion(
        key="friction",
        decision_type=DecisionType.CHOICE,
        instructions=(
            "What kind of interpersonal friction, if any, does this message "
            "carry toward the other person?"
        ),
        criteria={
            "none": "no friction; ordinary conversation",
            "criticism": "attacks the other person's character rather than an action",
            "defensiveness": "deflects blame, makes excuses, counter-attacks",
            "contempt": "mockery, sneering, name-calling, condescension",
        },
    ),
    DecisionQuestion(
        key="is_repair",
        decision_type=DecisionType.NOUL,
        instructions=(
            "Is the sender apologizing, making peace, or trying to defuse "
            "tension?"
        ),
    ),
    DecisionQuestion(
        key="sarcasm",
        decision_type=DecisionType.SCORE,
        instructions=(
            "How sarcastic or passive-aggressive is this message — saying one "
            "thing while meaning another?"
        ),
        levels=(
            "genuine and straightforward; says what it means",
            "a light edge, teasing, mild irony",
            "clearly sarcastic or pointed",
            "heavily sarcastic, barbed, passive-aggressive",
        ),
    ),
    DecisionQuestion(
        key="discourse_act",
        decision_type=DecisionType.CHOICE,
        instructions="What is this message doing, as a conversational move?",
        criteria={
            "statement": "states, informs, reacts, or acknowledges",
            "closed_question": "asks something answerable with yes, no, or a fact",
            "open_question_or_vulnerability": (
                "invites the other person to open up, or discloses something "
                "personal or vulnerable"
            ),
        },
    ),
)

#: Asked of a reply, with the message it answers, to see whether the reply met
#: the bid in it. Gottman's "turning toward" against "turning away".
RESPONSE_QUESTIONS: Sequence[DecisionQuestion] = (
    DecisionQuestion(
        key="turns_toward",
        decision_type=DecisionType.NOUL,
        instructions=(
            "Does this response acknowledge, engage with, or validate what the "
            "previous message said, rather than ignoring or brushing it off?"
        ),
    ),
)
