"""
Log handler for real-time log streaming
"""
import logging
from collections import deque
from datetime import datetime
from typing import List, Dict

class InMemoryLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory for API access"""
    
    def __init__(self, max_logs: int = 500):
        super().__init__()
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        
    def emit(self, record: logging.LogRecord):
        """Store log record in memory"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record)
        }
        self.logs.append(log_entry)
    
    def get_logs(self, limit: int = 100, level: str | None = None) -> List[Dict]:
        """Get recent logs, optionally filtered by level"""
        logs = list(self.logs)
        
        if level:
            logs = [log for log in logs if log["level"] == level.upper()]
        
        return logs[-limit:]
    
    def clear_logs(self):
        """Clear all stored logs"""
        self.logs.clear()

# Global instance
_log_handler = None

def get_log_handler() -> InMemoryLogHandler:
    """Get or create the global log handler instance"""
    global _log_handler
    if _log_handler is None:
        _log_handler = InMemoryLogHandler()
        # Set format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        _log_handler.setFormatter(formatter)
    return _log_handler

def setup_log_handler():
    """Attach the log handler to the root logger"""
    handler = get_log_handler()
    root_logger = logging.getLogger()
    
    # Only add if not already added
    if handler not in root_logger.handlers:
        root_logger.addHandler(handler)
