from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import get_current_user, get_current_user_sse

from .config import get_settings
from .db import append_chat, create_session, get_session, init_db, list_sessions,get_session_for_user
from .events import subscribe_session, unsubscribe_session
from .logger import get_logger, setup_logging
from .models import ChatRequest, ChatResponse, SessionCreate, SessionDetail, SessionSummary
from .workflow.graph import answer_followup, run_research_workflow

settings = get_settings()
logger = get_logger("main")
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up the application")
    init_db()
    logger.info("Database initialized successfully")
    yield
    # Shutdown
    logger.info("Shutting down the application")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://company-research-copilot-48tw1swnz-revanth2909.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    logger.debug("Health check endpoint called")
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionDetail)
def create_research_session(payload: SessionCreate, background_tasks: BackgroundTasks,user=Depends(get_current_user)):
    logger.info(f"Creating new research session for company: {payload.company_name}")
    logger.debug(f"Session details - Website: {payload.website}, Objective: {payload.objective}, Auto-run: {payload.auto_run}")
    
    session_id = str(uuid4())
    clerk_user_id = user["sub"] 
    session = create_session(session_id,clerk_user_id, payload.company_name, str(payload.website), payload.objective)
    logger.info(f"Session created successfully with ID: {session_id}")
    
    if payload.auto_run:
        logger.info(f"Auto-run enabled. Scheduling research workflow for session {session_id}")
        background_tasks.add_task(run_research_workflow, session_id)
    
    return session


@app.get("/sessions", response_model=list[SessionSummary])
def sessions(user=Depends(get_current_user)):
    logger.debug("Fetching all sessions")
    sessions_list = list_sessions(user["sub"])
    logger.debug(f"Retrieved {len(sessions_list)} sessions")
    return sessions_list


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: str,user=Depends(get_current_user)):
    logger.debug(f"Fetching session details for session_id: {session_id}")
    try:
        
        session = get_session_for_user(
            session_id,
            user["sub"]
        )
        logger.debug(f"Session found - Status: {session.get('status')}, Company: {session.get('company_name')}")
        return session
    except KeyError as exc:
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.get("/sessions/{session_id}/events")
async def session_events(session_id: str, user=Depends(get_current_user_sse)):
    logger.info(f"Client subscribed to events for session_id: {session_id}")
    try:
        session = get_session_for_user(
            session_id,
            user["sub"]
        )
        logger.debug(f"Session validation successful for {session_id}")
    except KeyError as exc:
        logger.warning(f"Failed to subscribe to events - Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found") from exc

    queue = subscribe_session(session_id)
    logger.debug(f"Event queue created for session {session_id}")

    async def event_generator():
        try:
            logger.debug(f"Event generator started for session {session_id}")
            initial = get_session_for_user(
                session_id,
                user["sub"]
            )
            logger.debug(f"Sending initial session state for {session_id}")
            yield f"data: {json.dumps({'type': 'session', 'session': initial})}\n\n"
            while True:
                event = await queue.get()
                logger.debug(f"Streaming event to client for session {session_id}: {event.get('type')}")
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logger.error(f"Error in event generator for session {session_id}: {exc}", exc_info=True)
        finally:
            logger.info(f"Client unsubscribed from events for session {session_id}")
            unsubscribe_session(session_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/sessions/{session_id}/run", response_model=SessionDetail)
def run_session(session_id: str, background_tasks: BackgroundTasks,user=Depends(get_current_user)):
    logger.info(f"Received run request for session_id: {session_id}")
    try:
        
        session = get_session_for_user(
            session_id,
            user["sub"]
        )

    except KeyError as exc:
        logger.warning(f"Run request failed - Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found") from exc
    
    logger.debug(f"Session status: {session['status']}")
    if session["status"] == "running":
        logger.info(f"Session {session_id} is already running, skipping duplicate request")
        return session
    
    logger.info(f"Scheduling research workflow for session {session_id}")
    background_tasks.add_task(run_research_workflow, session_id)
    return session


@app.post("/sessions/{session_id}/chat", response_model=ChatResponse)
def chat(session_id: str, payload: ChatRequest,user=Depends(get_current_user)):

    chat_logger = get_logger("chat")
    chat_logger.info(f"Chat message received for session_id: {session_id}")
    chat_logger.debug(f"User message: {payload.message[:100]}..." if len(payload.message) > 100 else f"User message: {payload.message}")
    
    try:
        
        session = get_session_for_user(
            session_id,
            user["sub"]
        )
        append_chat(session_id, "user", payload.message)
        chat_logger.debug(f"User message appended to chat history for session {session_id}")
        
        logger.info(f"Generating followup answer for session {session_id}")
        answer = answer_followup(session_id, payload.message)
        chat_logger.debug(f"Answer generated: {answer[:100]}..." if len(answer) > 100 else f"Answer generated: {answer}")
        
        append_chat(session_id, "assistant", answer)
        chat_logger.debug(f"Assistant response appended to chat history for session {session_id}")
        chat_logger.info(f"Chat exchange completed successfully for session {session_id}")
        
        return ChatResponse(answer=answer)
    except KeyError as exc:
        chat_logger.error(f"Session not found during chat: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except Exception as exc:
        chat_logger.error(f"Error during chat exchange for session {session_id}: {exc}", exc_info=True)
        raise
