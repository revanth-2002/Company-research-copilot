"""
Logging configuration for the research workflow application.
Sets up structured logging with both console and file handlers.
"""

import logging
import logging.handlers
from pathlib import Path

from .config import get_settings


def setup_logging() -> logging.Logger:
    """
    Configure logging for the application.
    Creates both console and file handlers with appropriate formatters.
    """
    logger = logging.getLogger("research_app")
    
    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Formatter with detailed information
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (rotating to prevent large files)
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "research_app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Session-specific file handler
    session_file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "sessions.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    session_file_handler.setLevel(logging.DEBUG)
    session_file_handler.setFormatter(formatter)
    
    # Create session logger
    session_logger = logging.getLogger("research_app.sessions")
    session_logger.addHandler(session_file_handler)
    session_logger.setLevel(logging.DEBUG)
    
    # Chat-specific file handler
    chat_file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "chat.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    chat_file_handler.setLevel(logging.DEBUG)
    chat_file_handler.setFormatter(formatter)
    
    # Create chat logger
    chat_logger = logging.getLogger("research_app.chat")
    chat_logger.addHandler(chat_file_handler)
    chat_logger.setLevel(logging.DEBUG)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name."""
    return logging.getLogger(f"research_app.{name}")
