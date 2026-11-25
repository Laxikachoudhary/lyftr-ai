
import os
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from app.database import (
    init_db,
    create_session,
    session_exists,
    add_message,
    get_session_messages,
    get_all_sessions,
    update_session_title,
)

from app.llm import generate_response, ProvidersUnavailableError

from app.schemas import (
    ChatRequest,
    ChatResponse,
    SessionMessagesResponse,
    CreateSessionResponse,
    SessionListResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Lyftr AI API",
    description="AI chatbot with provider failover, caching and chat history",
    version="1.1.0",
    lifespan=lifespan,
)


allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Create a new conversation
@app.post("/sessions", response_model=CreateSessionResponse)
async def new_session():
    session_id = str(uuid.uuid4())

    create_session(session_id)

    return CreateSessionResponse(
        session_id=session_id,
        title="New Chat",
    )


# Get all previous conversations
@app.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    sessions = get_all_sessions()

    return SessionListResponse(sessions=sessions)


# Send a chat message
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_simulate_failure: str = Header(
        default="",
        alias="X-Simulate-Failure"
    ),
):
    session_id = request.session_id or str(uuid.uuid4())

    # Create session if it doesn't exist
    if not session_exists(session_id):
        title = request.message.strip()[:40]
        create_session(session_id, title=title)

    previous_messages = get_session_messages(session_id)

    # Set title using the first message
    if not previous_messages:
        title = request.message.strip().replace("\n", " ")[:40]
        update_session_title(session_id, title)

    messages = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in previous_messages
    ]

    messages.append({
        "role": "user",
        "content": request.message,
    })

    add_message(
        session_id=session_id,
        role="user",
        content=request.message,
    )

    simulation_enabled = (
        os.getenv("ENABLE_FAILURE_SIMULATION", "false").lower()
        == "true"
    )

    failure_header = (
        x_simulate_failure if simulation_enabled else ""
    )

    start_time = time.perf_counter()

    try:
        result = await generate_response(
            messages=messages,
            failure_header=failure_header,
        )

    except ProvidersUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable",
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="internal server error",
        )

    latency_ms = (time.perf_counter() - start_time) * 1000

    add_message(
        session_id=session_id,
        role="assistant",
        content=result["response"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        model=result["model"],
        latency_ms=latency_ms,
        key_id=result["key_id"],
        fallback_attempts=result["fallback_attempts"],
        response_source=result["response_source"],
    )

    return ChatResponse(
        session_id=session_id,
        response=result["response"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        model=result["model"],
        latency_ms=round(latency_ms, 2),
        key_id=result["key_id"],
        fallback_attempts=result["fallback_attempts"],
        response_source=result["response_source"],
    )


# Get messages from a particular conversation
@app.get(
    "/sessions/{session_id}/messages",
    response_model=SessionMessagesResponse,
)
async def get_messages(session_id: str):
    if not session_exists(session_id):
        raise HTTPException(
            status_code=404,
            detail="session not found",
        )

    messages = get_session_messages(session_id)

    return SessionMessagesResponse(
        session_id=session_id,
        messages=messages,
    )
