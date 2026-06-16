from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from .config import get_settings
from .events import broadcast_session_event
from .logger import get_logger

logger = get_logger("database")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mongo_client() -> MongoClient:
    return MongoClient(get_settings().database_url)


def _sessions_collection():
    client = _mongo_client()
    db = client.get_default_database()
    return db.sessions


def init_db() -> None:
    logger.info("Initializing database")
    try:
        collection = _sessions_collection()
        collection.create_index([("id", ASCENDING)], unique=True)
        collection.create_index([("user_id", ASCENDING)])
        collection.create_index([("updated_at", DESCENDING)])
        logger.info("Database initialized successfully")
    except Exception as exc:
        logger.error(f"Failed to initialize database: {exc}", exc_info=True)
        raise


def _normalize_session(doc: dict[str, Any]) -> dict[str, Any]:
    if doc is None:
        raise KeyError("Session not found")

    session = {k: v for k, v in doc.items() if k != "_id"}
    session.setdefault("progress", [])
    session.setdefault("errors", [])
    session.setdefault("chat", [])
    session["report"] = session.get("report")
    return session


def create_session(session_id: str, user_id:str,company_name: str, website: str, objective: str) -> dict[str, Any]:
    logger.info(f"Creating session: {session_id}")
    logger.debug(f"Session details - Company: {company_name}, Website: {website}")

    timestamp = now_iso()
    session_data = {
        "id": session_id,
        "user_id": user_id,
        "company_name": company_name,
        "website": website,
        "objective": objective,
        "status": "queued",
        "progress": [],
        "errors": [],
        "chat": [],
        "report": None,
        "created_at": timestamp,
        "updated_at": timestamp,
    }

    try:
        collection = _sessions_collection()
        collection.insert_one(session_data)
        logger.info(f"Session created successfully: {session_id}")
        return get_session(session_id)
    except DuplicateKeyError as exc:
        logger.error(f"Session already exists: {session_id}", exc_info=True)
        raise
    except Exception as exc:
        logger.error(f"Failed to create session {session_id}: {exc}", exc_info=True)
        raise


def list_sessions(user_id:str) -> list[dict[str, Any]]:
    logger.debug("Fetching all sessions from database")
    try:
        collection = _sessions_collection()
        cursor = collection.find(
            {"user_id": user_id},
            {"_id": False, "id": True,"user_id":True, "company_name": True, "website": True, "objective": True, "status": True, "created_at": True, "updated_at": True},
        ).sort("updated_at", DESCENDING)
        sessions_list = [doc for doc in cursor]
        logger.debug(f"Retrieved {len(sessions_list)} sessions")
        return sessions_list
    except Exception as exc:
        logger.error(f"Failed to list sessions: {exc}", exc_info=True)
        raise


def get_session(session_id: str) -> dict[str, Any]:
    logger.debug(f"Fetching session: {session_id}")
    try:
        collection = _sessions_collection()
        doc = collection.find_one({"id": session_id})
        if doc is None:
            logger.warning(f"Session not found: {session_id}")
            raise KeyError(session_id)

        session = _normalize_session(doc)
        logger.debug(f"Session retrieved successfully - Status: {session.get('status')}")
        return session
    except KeyError:
        raise
    except Exception as exc:
        logger.error(f"Failed to get session {session_id}: {exc}", exc_info=True)
        raise

def get_session_for_user(
    session_id: str,
    user_id: str,
) -> dict[str, Any]:

    collection = _sessions_collection()

    doc = collection.find_one(
        {
            "id": session_id,
            "user_id": user_id,
        }
    )

    if doc is None:
        raise KeyError(session_id)

    return _normalize_session(doc)

def update_session(session_id: str, **fields: Any) -> dict[str, Any]:
    logger.debug(f"Updating session {session_id} with fields: {list(fields.keys())}")

    if not fields:
        logger.debug(f"No fields to update for session {session_id}")
        return get_session(session_id)

    fields["updated_at"] = now_iso()
    try:
        collection = _sessions_collection()
        result = collection.update_one({"id": session_id}, {"$set": fields})
        if result.matched_count == 0:
            logger.warning(f"Session not found: {session_id}")
            raise KeyError(session_id)

        logger.debug(f"Session {session_id} updated successfully")
        session = get_session(session_id)
        if "status" in fields:
            logger.info(f"Session {session_id} status updated to: {fields['status']}")

        broadcast_session_event(session_id, {"type": "session", "session": session})
        logger.debug(f"Session update event broadcasted for {session_id}")
        return session
    except KeyError:
        raise
    except Exception as exc:
        logger.error(f"Failed to update session {session_id}: {exc}", exc_info=True)
        raise


def append_progress(session_id: str, node: str, status: str, message: str, payload: dict | None = None) -> None:
    logger.debug(f"[{session_id}] Appending progress - Node: {node}, Status: {status}")
    try:
        session = get_session(session_id)
        progress = session["progress"]
        progress.append(
            {
                "node": node,
                "status": status,
                "message": message,
                "payload": payload or {},
                "timestamp": now_iso(),
            }
        )
        logger.debug(f"[{session_id}] Progress event created: {message}")
        update_session(session_id, progress=progress)
        logger.debug(f"[{session_id}] Progress updated successfully")
    except Exception as exc:
        logger.error(f"[{session_id}] Failed to append progress for node {node}: {exc}", exc_info=True)
        raise


def append_chat(session_id: str, role: str, content: str) -> list[dict[str, str]]:
    chat_logger = get_logger("chat")
    chat_logger.debug(f"[{session_id}] Appending chat message - Role: {role}")
    chat_logger.debug(f"[{session_id}] Message: {content[:100]}..." if len(content) > 100 else f"[{session_id}] Message: {content}")

    try:
        session = get_session(session_id)
        chat = session["chat"]
        chat.append({"role": role, "content": content, "timestamp": now_iso()})
        chat_logger.debug(f"[{session_id}] Chat message added, total messages: {len(chat)}")
        update_session(session_id, chat=chat)
        chat_logger.debug(f"[{session_id}] Chat history updated successfully")
        return chat
    except Exception as exc:
        chat_logger.error(f"[{session_id}] Failed to append chat message from {role}: {exc}", exc_info=True)
        raise
