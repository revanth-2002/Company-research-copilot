import asyncio
from typing import Any, Dict, List

from .logger import get_logger

logger = get_logger("events")

_session_subscribers: Dict[str, List[asyncio.Queue[Dict[str, Any]]]] = {}


def subscribe_session(session_id: str) -> asyncio.Queue[Dict[str, Any]]:

    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    subscribers = _session_subscribers.setdefault(session_id, [])
    subscribers.append(queue)
    logger.info(f"[{session_id}] New subscriber added, total subscribers: {len(subscribers)}")
    return queue

def unsubscribe_session(session_id: str, queue: asyncio.Queue[Dict[str, Any]]) -> None:

    subscribers = _session_subscribers.get(session_id)
    if not subscribers:
        logger.warning(f"[{session_id}] No subscribers found for unsubscribe")
        return
    try:
        subscribers.remove(queue)
        logger.info(f"[{session_id}] Subscriber removed, remaining subscribers: {len(subscribers)}")
    except ValueError:
        logger.warning(f"[{session_id}] Queue not found in subscribers list")
        pass
    if not subscribers:
        _session_subscribers.pop(session_id, None)
        logger.debug(f"[{session_id}] All subscribers removed, cleaning up session")

def broadcast_session_event(session_id: str, event: Dict[str, Any]) -> None:

    subscribers = list(_session_subscribers.get(session_id, []))
    logger.debug(f"[{session_id}] Broadcasting event to {len(subscribers)} subscribers - Event type: {event.get('type')}")
    
    delivered = 0
    failed = 0
    
    for queue in subscribers:
        try:
            queue.put_nowait(event)
            delivered += 1
        except asyncio.QueueFull:
            logger.warning(f"[{session_id}] Queue is full, dropping event for subscriber")
            failed += 1
    
    if failed > 0:
        logger.debug(f"[{session_id}] Event broadcast completed - Delivered: {delivered}, Failed: {failed}")
    else:
        logger.debug(f"[{session_id}] Event broadcast completed - Delivered to all {delivered} subscribers")
