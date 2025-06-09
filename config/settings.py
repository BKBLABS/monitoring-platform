"""
Configuration Management System for Monitoring Platform
Supports environment-based configuration, validation, and secret management
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 3306
    username: str = "monitoring_user"
    password: str = ""
    database: str = "monitoring_db"
    connection_pool_size: int = 10
    connection_timeout: int = 30
    
    def get_connection_string(self) -> str:
        """Generate MySQL connection string"""
        return f"mysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class ZabbixConfig:
    """Zabbix integration configuration"""
    url: str = "http://localhost/api_jsonrpc.php"
    username: str = "Admin"
    password: str = ""
    host_id: str = "10105"
    timeout: int = 30
    retry_attempts: int = 3


@dataclass
class HyphenMonConfig:
    """HyphenMon integration configuration"""
    api_url: str = "http://localhost:5001"
    timeout: int = 15
    retry_attempts: int = 3
    metrics_endpoint: str = "/metrics"
    health_check_endpoint: str = "/health"


@dataclass
class AlertingConfig:
    """Alerting system configuration"""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    to_emails: list = field(default_factory=list)
    use_tls: bool = True
    timeout: int = 30


@dataclass
class ProcessingConfig:
    """Data processing configuration"""
    correlation_window_seconds: int = 10
    data_fetch_interval_minutes: int = 5
    anomaly_detection_threshold: float = 0.5
    batch_size: int = 1000
    max_processing_threads: int = 4


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size_mb: int = 10
    backup_count: int = 5
    enable_json_logging: bool = False


class ConfigManager:
    """Centralized configuration management system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config_cache = {}
        self.load_configuration()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return os.path.join(os.path.dirname(__file__), "config.json")
    
    def load_configuration(self) -> None:
        """Load configuration from file and environment variables"""
        # Load from file if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)
                self._config_cache.update(file_config)
            except Exception as e:
                logging.warning(f"Failed to load config file {self.config_path}: {e}")
        
        # Override with environment variables
        self._load_env_variables()
    
    def _load_env_variables(self) -> None:
        """Load configuration from environment variables"""
        env_mappings = {
            # Database
            "MYSQL_HOST": ("database", "host"),
            "MYSQL_PORT": ("database", "port"),
            "MYSQL_USER": ("database", "username"),
            "MYSQL_PASSWORD": ("database", "password"),
            "MYSQL_DATABASE": ("database", "database"),
            
            # Zabbix
            "ZABBIX_URL": ("zabbix", "url"),
            "ZABBIX_USER": ("zabbix", "username"),
            "ZABBIX_PASSWORD": ("zabbix", "password"),
            "ZABBIX_HOST_ID": ("zabbix", "host_id"),
            
            # HyphenMon
            "HYPHENMON_URL": ("hyphenmon", "api_url"),
            "HYPHENMON_TIMEOUT": ("hyphenmon", "timeout"),
            
            # Alerting
            "SMTP_SERVER": ("alerting", "smtp_server"),
            "SMTP_PORT": ("alerting", "smtp_port"),
            "SMTP_USER": ("alerting", "smtp_username"),
            "SMTP_PASSWORD": ("alerting", "smtp_password"),
            "FROM_EMAIL": ("alerting", "from_email"),
            "TO_EMAILS": ("alerting", "to_emails"),
            
            # Processing
            "CORRELATION_WINDOW": ("processing", "correlation_window_seconds"),
            "DATA_FETCH_INTERVAL": ("processing", "data_fetch_interval_minutes"),
            "ANOMALY_THRESHOLD": ("processing", "anomaly_detection_threshold"),
            
            # Logging
            "LOG_LEVEL": ("logging", "level"),
            "LOG_FILE": ("logging", "file_path"),
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if section not in self._config_cache:
                    self._config_cache[section] = {}
                
                # Type conversion
                if key in ["port", "timeout", "correlation_window_seconds", "data_fetch_interval_minutes"]:
                    value = int(value)
                elif key in ["anomaly_detection_threshold"]:
                    value = float(value)
                elif key == "to_emails":
                    value = value.split(",") if value else []
                
                self._config_cache[section][key] = value
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        db_config = self._config_cache.get("database", {})
        return DatabaseConfig(**db_config)
    
    def get_zabbix_config(self) -> ZabbixConfig:
        """Get Zabbix configuration"""
        zabbix_config = self._config_cache.get("zabbix", {})
        return ZabbixConfig(**zabbix_config)
    
    def get_hyphenmon_config(self) -> HyphenMonConfig:
        """Get HyphenMon configuration"""
        hyphenmon_config = self._config_cache.get("hyphenmon", {})
        return HyphenMonConfig(**hyphenmon_config)
    
    def get_alerting_config(self) -> AlertingConfig:
        """Get alerting configuration"""
        alerting_config = self._config_cache.get("alerting", {})
        return AlertingConfig(**alerting_config)
    
    def get_processing_config(self) -> ProcessingConfig:
        """Get processing configuration"""
        processing_config = self._config_cache.get("processing", {})
        return ProcessingConfig(**processing_config)
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration"""
        logging_config = self._config_cache.get("logging", {})
        return LoggingConfig(**logging_config)
    
    def validate_configuration(self) -> list:
        """Validate configuration and return list of issues"""
        issues = []
        
        # Validate database config
        db_config = self.get_database_config()
        if not db_config.host:
            issues.append("Database host is required")
        if not db_config.username:
            issues.append("Database username is required")
        if not db_config.database:
            issues.append("Database name is required")
        
        # Validate required passwords (in production)
        if os.getenv("ENVIRONMENT") == "production":
            if not db_config.password:
                issues.append("Database password is required in production")
            
            zabbix_config = self.get_zabbix_config()
            if not zabbix_config.password:
                issues.append("Zabbix password is required in production")
        
        return issues
    
    def save_configuration(self) -> None:
        """Save current configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config_cache, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save configuration: {e}")
    
    def reload_configuration(self) -> None:
        """Reload configuration from file and environment"""
        self._config_cache.clear()
        self.load_configuration()


# Global configuration manager instance
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    return config_manager


if __name__ == "__main__":
    # Example usage and validation
    config = get_config()
    
    print("Database Config:", config.get_database_config())
    print("Zabbix Config:", config.get_zabbix_config())
    print("HyphenMon Config:", config.get_hyphenmon_config())
    print("Alerting Config:", config.get_alerting_config())
    print("Processing Config:", config.get_processing_config())
    print("Logging Config:", config.get_logging_config())
    
    issues = config.validate_configuration()
    if issues:
        print("\nConfiguration Issues:")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("\n✅ Configuration is valid!")
