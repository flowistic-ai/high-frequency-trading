"""
Centralized logging configuration for the crypto HFT tool.
This module should be imported once at the application startup to configure logging.
"""
import logging
import os
from typing import Optional


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None,
    log_file: Optional[str] = None
) -> None:
    """
    Configure logging for the entire application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        log_file: Optional file to write logs to
    """
    # Get level from parameter, environment, or default to INFO
    if level is None:
        level = os.getenv('LOG_LEVEL', 'INFO')
    
    # Default format string
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        filename=log_file,
        filemode='a' if log_file else None,
        force=True  # Override any existing configuration
    )
    
    # Set specific loggers for external libraries to reduce noise
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Usually __name__ from the calling module
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name) 