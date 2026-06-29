"""Structured logging with Application Insights integration."""

import structlog
import inspect
from pathlib import Path
from datetime import datetime
import pytz
import sys


class CustomFormatter:
    """Custom formatter for human-readable log output."""
    
    def __init__(self):
        self.ist_tz = pytz.timezone('Asia/Kolkata')
    
    def __call__(self, _, __, event_dict):
        """
        Format log output as:
        TIMESTAMP_IST :: LEVEL :: request_id :: org_name :: Folder :: File :: Function :: Line :: [message]
        """
        # Get timestamp in IST
        timestamp = datetime.now(self.ist_tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract fields
        level = event_dict.get('level', 'INFO').upper()
        request_id = event_dict.get('request_id', '-')
        org_name = event_dict.get('org_name', '-')
        folder = event_dict.get('folder', '-')
        filename = event_dict.get('filename', '-')
        function = event_dict.get('function', '-')
        line = event_dict.get('line', '-')
        message = event_dict.get('event', '')
        
        # Format output
        log_line = (
            f"{timestamp} :: {level} :: {request_id} :: {org_name} :: "
            f"{folder} :: {filename} :: {function} :: {line} :: [{message}]"
        )
        
        # If there's exception info, append it
        if 'exception' in event_dict:
            log_line += f"\n{event_dict['exception']}"
        
        return log_line


def setup_logging():
    """Configure structured logging with custom format."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            CustomFormatter(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(filename: str = None):
    """
    Get a logger instance with automatic filename detection.
    
    Args:
        filename: Optional filename. If not provided, automatically detected from caller.
    
    Returns:
        Bound logger with filename and folder context
    """
    if not filename:
        frame = inspect.currentframe().f_back
        filepath = frame.f_code.co_filename
        file_path = Path(filepath)
        filename = file_path.name
        folder = file_path.parent.name
    else:
        # Extract folder from filename if it contains path
        file_path = Path(filename)
        filename = file_path.name
        folder = file_path.parent.name if file_path.parent.name else '-'
    
    return structlog.get_logger().bind(filename=filename, folder=folder)


class LoggerAdapter:
    """
    Logger adapter that automatically captures function and line information.
    """
    def __init__(self, logger, filename=None, folder=None):
        self._logger = logger
        self._filename = filename or '-'
        self._folder = folder or '-'
    
    def _get_caller_info(self):
        """Get caller function name and line number."""
        # Go back 3 frames: _get_caller_info -> _add_context -> info/warning/etc -> user code
        frame = inspect.currentframe().f_back.f_back.f_back
        function_name = frame.f_code.co_name
        line_number = frame.f_lineno
        return function_name, line_number
    
    def _add_context(self, **kwargs):
        """Add automatic context to kwargs."""
        function_name, line_number = self._get_caller_info()
        kwargs.update({
            'function': function_name,
            'line': line_number,
            'filename': self._filename,
            'folder': self._folder,
        })
        return kwargs
    
    def debug(self, msg, **kwargs):
        """Log debug message."""
        kwargs = self._add_context(**kwargs)
        self._logger.debug(msg, **kwargs)
    
    def info(self, msg, **kwargs):
        """Log info message."""
        kwargs = self._add_context(**kwargs)
        self._logger.info(msg, **kwargs)
    
    def warning(self, msg, **kwargs):
        """Log warning message."""
        kwargs = self._add_context(**kwargs)
        self._logger.warning(msg, **kwargs)
    
    def error(self, msg, **kwargs):
        """Log error message."""
        kwargs = self._add_context(**kwargs)
        self._logger.error(msg, **kwargs)
    
    def critical(self, msg, **kwargs):
        """Log critical message."""
        kwargs = self._add_context(**kwargs)
        self._logger.critical(msg, **kwargs)
    
    def exception(self, msg, **kwargs):
        """Log exception with traceback."""
        import traceback
        kwargs['exception'] = traceback.format_exc()
        kwargs = self._add_context(**kwargs)
        self._logger.error(msg, **kwargs)


def get_logger_with_context(filename: str = None):
    """
    Get a logger instance with automatic context detection.
    Returns LoggerAdapter that captures function and line info automatically.
    
    Args:
        filename: Optional filename. If not provided, automatically detected from caller.
    
    Returns:
        LoggerAdapter instance with automatic context binding
    """
    if not filename:
        frame = inspect.currentframe().f_back
        filepath = frame.f_code.co_filename
        file_path = Path(filepath)
        filename = file_path.name
        folder = file_path.parent.name
    else:
        file_path = Path(filename)
        filename = file_path.name
        folder = file_path.parent.name if file_path.parent.name else '-'
    
    base_logger = structlog.get_logger()
    return LoggerAdapter(base_logger, filename=filename, folder=folder)


def log_function_entry(logger_instance, function_name: str, **kwargs):
    """Log function entry with parameters."""
    # Get caller info
    frame = inspect.currentframe().f_back
    line_number = frame.f_lineno
    
    if hasattr(logger_instance, '_logger'):
        # LoggerAdapter instance
        logger_instance._logger.info(
            f"Entering {function_name}",
            function=function_name,
            line=line_number,
            action="entry",
            filename=logger_instance._filename,
            folder=logger_instance._folder,
            **kwargs
        )
    else:
        # Direct logger instance
        logger_instance.info(
            f"Entering {function_name}",
            function=function_name,
            line=line_number,
            action="entry",
            **kwargs
        )


def log_function_exit(logger_instance, function_name: str, **kwargs):
    """Log function exit with return details."""
    # Get caller info
    frame = inspect.currentframe().f_back
    line_number = frame.f_lineno
    
    if hasattr(logger_instance, '_logger'):
        # LoggerAdapter instance
        logger_instance._logger.info(
            f"Exiting {function_name}",
            function=function_name,
            line=line_number,
            action="exit",
            filename=logger_instance._filename,
            folder=logger_instance._folder,
            **kwargs
        )
    else:
        # Direct logger instance
        logger_instance.info(
            f"Exiting {function_name}",
            function=function_name,
            line=line_number,
            action="exit",
            **kwargs
        )


# Legacy logger for backward compatibility
logger = structlog.get_logger().bind(filename="-", folder="-", function="-", line="-")
