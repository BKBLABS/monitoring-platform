"""
Enhanced logging system for monitoring platform with structured logging,
performance metrics, and multiple output formats
"""

import logging
import logging.handlers
import json
import time
import os
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

from config.settings import get_config


@dataclass
class LogEntry:
    """Structured log entry for JSON logging"""
    timestamp: str
    level: str
    logger_name: str
    message: str
    component: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    performance_data: Optional[Dict[str, Any]] = None
    extra_data: Optional[Dict[str, Any]] = None


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat() + 'Z',
            level=record.levelname,
            logger_name=record.name,
            message=record.getMessage(),
            component=getattr(record, 'component', 'unknown'),
            request_id=getattr(record, 'request_id', None),
            user_id=getattr(record, 'user_id', None),
            performance_data=getattr(record, 'performance_data', None),
            extra_data=getattr(record, 'extra_data', None)
        )
        
        # Add exception info if present
        log_dict = asdict(log_entry)
        if record.exc_info:
            log_dict['exception'] = self.formatException(record.exc_info)
        
        # Remove None values for cleaner JSON
        log_dict = {k: v for k, v in log_dict.items() if v is not None}
        
        return json.dumps(log_dict)


class PerformanceLogger:
    """Performance logging utility for monitoring execution times"""
    
    def __init__(self, logger: logging.Logger, operation_name: str):
        self.logger = logger
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(
            f"Starting operation: {self.operation_name}",
            extra={'component': 'performance', 'operation': self.operation_name}
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time
        
        performance_data = {
            'operation': self.operation_name,
            'execution_time_seconds': round(execution_time, 4),
            'success': exc_type is None
        }
        
        if exc_type is None:
            self.logger.info(
                f"Completed operation: {self.operation_name} in {execution_time:.4f}s",
                extra={
                    'component': 'performance',
                    'performance_data': performance_data
                }
            )
        else:
            performance_data['error_type'] = exc_type.__name__
            self.logger.error(
                f"Failed operation: {self.operation_name} after {execution_time:.4f}s",
                extra={
                    'component': 'performance',
                    'performance_data': performance_data
                },
                exc_info=True
            )


class MonitoringPlatformLogger:
    """Enhanced logger for the monitoring platform"""
    
    def __init__(self, name: str, component: str = None):
        self.component = component or name
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self):
        """Configure logger based on configuration settings"""
        config = get_config()
        log_config = config.get_logging_config()
        
        # Set log level
        level = getattr(logging, log_config.level.upper(), logging.INFO)
        self.logger.setLevel(level)
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        
        if log_config.enable_json_logging:
            console_handler.setFormatter(JSONFormatter())
        else:
            console_handler.setFormatter(logging.Formatter(log_config.format))
        
        self.logger.addHandler(console_handler)
        
        # File handler if specified
        if log_config.file_path:
            os.makedirs(os.path.dirname(log_config.file_path), exist_ok=True)
            
            file_handler = logging.handlers.RotatingFileHandler(
                log_config.file_path,
                maxBytes=log_config.max_file_size_mb * 1024 * 1024,
                backupCount=log_config.backup_count
            )
            
            if log_config.enable_json_logging:
                file_handler.setFormatter(JSONFormatter())
            else:
                file_handler.setFormatter(logging.Formatter(log_config.format))
            
            self.logger.addHandler(file_handler)
    
    def performance_timer(self, operation_name: str) -> PerformanceLogger:
        """Create a performance timer context manager"""
        return PerformanceLogger(self.logger, operation_name)
    
    def log_with_context(self, level: str, message: str, **context):
        """Log with additional context information"""
        extra = {
            'component': self.component,
            'extra_data': context
        }
        
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(message, extra=extra)
    
    def debug(self, message: str, **context):
        """Log debug message with context"""
        self.log_with_context('debug', message, **context)
    
    def info(self, message: str, **context):
        """Log info message with context"""
        self.log_with_context('info', message, **context)
    
    def warning(self, message: str, **context):
        """Log warning message with context"""
        self.log_with_context('warning', message, **context)
    
    def error(self, message: str, exc_info=None, **context):
        """Log error message with context and optional exception info"""
        extra = {
            'component': self.component,
            'extra_data': context
        }
        self.logger.error(message, extra=extra, exc_info=exc_info)
    
    def critical(self, message: str, exc_info=None, **context):
        """Log critical message with context and optional exception info"""
        extra = {
            'component': self.component,
            'extra_data': context
        }
        self.logger.critical(message, extra=extra, exc_info=exc_info)


# Factory function for creating loggers
def get_logger(name: str, component: str = None) -> MonitoringPlatformLogger:
    """Get or create a logger instance for the monitoring platform"""
    return MonitoringPlatformLogger(name, component)


# Pre-configured loggers for common components
hyphenmon_logger = get_logger('hyphenmon', 'hyphenmon-service')
aggregator_logger = get_logger('data-aggregator', 'data-aggregator')
correlator_logger = get_logger('correlator', 'correlation-engine')
anomaly_logger = get_logger('anomaly-detector', 'anomaly-detection')
alerting_logger = get_logger('alerting-system', 'alerting-system')
processor_logger = get_logger('main-processor', 'orchestration')


if __name__ == "__main__":
    # Example usage and testing
    logger = get_logger('test', 'test-component')
    
    # Basic logging
    logger.info("System initialized successfully")
    logger.warning("High memory usage detected", memory_usage_percent=85.2)
    
    # Performance logging
    with logger.performance_timer("database_query"):
        time.sleep(0.1)  # Simulate operation
    
    # Error logging
    try:
        raise ValueError("Test error")
    except ValueError as e:
        logger.error("Test error occurred", exc_info=True, error_code="TEST001")
    
    print("✅ Logger testing completed successfully!")