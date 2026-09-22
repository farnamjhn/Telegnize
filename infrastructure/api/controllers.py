from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.api.dependencies import get_message_repo as get_repository
from infrastructure.api.routers.analytics import router as analytics_router
from infrastructure.api.routers.chats import router as chats_router
from infrastructure.api.routers.decisions import router as decisions_router
from infrastructure.api.routers.messages import router as messages_router

# FastAPI application instance
app = FastAPI(
    title="Telegnize API",
    version="0.2.0",
    description="Telegram Chat Analyzer Intelligence with Laya System 1 decision engine and multilingual NLP",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chats_router, prefix="/api")
app.include_router(messages_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(decisions_router, prefix="/api")

# Also include messages_router directly without /api prefix for backward compatibility with existing tests
app.include_router(messages_router)


@app.get("/", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "app": "Telegnize API",
        "version": "0.2.0",
        "capabilities": [
            "ijson_streaming",
            "hazm_persian_normalization",
            "nltk_english_normalization",
            "sqlite3_persistence",
            "laya_system1_decision_engine",
        ],
    }
