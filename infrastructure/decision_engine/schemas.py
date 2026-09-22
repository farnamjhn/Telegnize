from typing import Any, Dict

# Pre-calibrated schematic typed questions for Laya System 1 Decision Engine

MESSAGE_TONE_QUESTIONS: Dict[str, Any] = {
    "tone": {
        "type": "choice",
        "instructions": "What is the emotional tone of this message?",
        "criteria": {
            "affectionate": "warm, loving, caring, affectionate, romantic",
            "friendly": "friendly, supportive, happy, enthusiastic",
            "casual": "everyday, relaxed, informal chat",
            "frustrated": "annoyed, complaining, upset, sarcastic",
            "neutral": "factual, simple statement, informative, without strong emotion"
        }
    },
    "is_conflict": {
        "type": "noul",
        "instructions": "Does this message express tension, argument, grievance, or interpersonal conflict?"
    }
}

CONVERSATION_DYNAMIC_QUESTIONS: Dict[str, Any] = {
    "relationship_dynamic": {
        "type": "choice",
        "instructions": "What best characterizes the interpersonal dynamic between the participants in this conversation snippet?",
        "criteria": {
            "close_friends": "frequent banter, casual intimacy, shared humor, comfort",
            "romantic": "affectionate, loving, caring, intimate emotional sharing",
            "colleagues": "work or task-oriented, structured, professional, informative",
            "acquaintances": "polite, courteous, formal, low intimacy"
        }
    },
    "overall_sentiment": {
        "type": "choice",
        "instructions": "What is the overall sentiment of this conversation exchange?",
        "criteria": {
            "positive": "harmonious, warm, playful, supportive",
            "neutral": "matter-of-fact, transactional, informational",
            "tense": "strained, irritated, conflicting, distant"
        }
    }
}
