"""The catalogue of questions Telegnize asks about conversations.

These are product decisions — what we want to know about a chat — so they live
in the application layer rather than next to the model that answers them.
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
