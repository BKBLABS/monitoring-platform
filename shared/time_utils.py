"""
Time utilities for monitoring platform with timezone handling,
timestamp conversion, and time window calculations
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Union, Optional, Tuple
import calendar

# Constants for common time intervals
MINUTE_SECONDS = 60
HOUR_SECONDS = 3600
DAY_SECONDS = 86400
WEEK_SECONDS = 604800


def get_current_timestamp() -> int:
    """Get current Unix timestamp in seconds"""
    return int(time.time())


def get_current_timestamp_ms() -> int:
    """Get current Unix timestamp in milliseconds"""
    return int(time.time() * 1000)


def get_current_utc_datetime() -> datetime:
    """Get current UTC datetime object"""
    return datetime.now(timezone.utc)


def get_current_iso_string() -> str:
    """Get current UTC time as ISO 8601 string"""
    return get_current_utc_datetime().isoformat()


def timestamp_to_datetime(timestamp: Union[int, float], 
                         use_utc: bool = True) -> datetime:
    """
    Convert Unix timestamp to datetime object
    
    Args:
        timestamp: Unix timestamp (seconds or milliseconds)
        use_utc: Whether to return UTC datetime (default: True)
    
    Returns:
        datetime object
    """
    # Handle milliseconds
    if timestamp > 1e10:  # Likely milliseconds
        timestamp = timestamp / 1000
    
    if use_utc:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    else:
        return datetime.fromtimestamp(timestamp)


def datetime_to_timestamp(dt: datetime) -> int:
    """
    Convert datetime object to Unix timestamp
    
    Args:
        dt: datetime object
    
    Returns:
        Unix timestamp in seconds
    """
    return int(dt.timestamp())


def iso_string_to_timestamp(iso_string: str) -> int:
    """
    Convert ISO 8601 string to Unix timestamp
    
    Args:
        iso_string: ISO 8601 formatted time string
    
    Returns:
        Unix timestamp in seconds
    """
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
    return datetime_to_timestamp(dt)


def get_time_window(
    window_size_minutes: int, 
    end_time: Optional[datetime] = None
) -> Tuple[datetime, datetime]:
    """
    Get start and end datetime for a time window
    
    Args:
        window_size_minutes: Size of the time window in minutes
        end_time: End time (default: current UTC time)
    
    Returns:
        Tuple of (start_time, end_time)
    """
    if end_time is None:
        end_time = get_current_utc_datetime()
    
    start_time = end_time - timedelta(minutes=window_size_minutes)
    return start_time, end_time


def get_time_window_timestamps(
    window_size_minutes: int, 
    end_timestamp: Optional[int] = None
) -> Tuple[int, int]:
    """
    Get start and end timestamps for a time window
    
    Args:
        window_size_minutes: Size of the time window in minutes
        end_timestamp: End timestamp (default: current timestamp)
    
    Returns:
        Tuple of (start_timestamp, end_timestamp)
    """
    if end_timestamp is None:
        end_timestamp = get_current_timestamp()
    
    start_timestamp = end_timestamp - (window_size_minutes * MINUTE_SECONDS)
    return start_timestamp, end_timestamp


def is_within_time_window(
    timestamp1: int, 
    timestamp2: int, 
    window_seconds: int = 10
) -> bool:
    """
    Check if two timestamps are within a specified time window
    
    Args:
        timestamp1: First timestamp
        timestamp2: Second timestamp
        window_seconds: Time window in seconds (default: 10)
    
    Returns:
        True if timestamps are within the window
    """
    return abs(timestamp1 - timestamp2) <= window_seconds


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted duration string
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def get_mysql_datetime_format(dt: datetime) -> str:
    """
    Format datetime for MySQL storage
    
    Args:
        dt: datetime object
    
    Returns:
        MySQL compatible datetime string
    """
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def get_mysql_timestamp_format(timestamp: int) -> str:
    """
    Convert timestamp to MySQL datetime format
    
    Args:
        timestamp: Unix timestamp
    
    Returns:
        MySQL compatible datetime string
    """
    dt = timestamp_to_datetime(timestamp)
    return get_mysql_datetime_format(dt)


def get_grafana_time_range(hours_back: int = 6) -> dict:
    """
    Get Grafana-compatible time range
    
    Args:
        hours_back: How many hours back from now
    
    Returns:
        Dictionary with 'from' and 'to' timestamps for Grafana
    """
    now = get_current_timestamp()
    from_time = now - (hours_back * HOUR_SECONDS)
    
    return {
        'from': from_time,
        'to': now
    }


def calculate_correlation_window_bounds(
    reference_timestamp: int, 
    window_seconds: int = 10
) -> Tuple[int, int]:
    """
    Calculate the bounds for correlation time window
    
    Args:
        reference_timestamp: Reference timestamp
        window_seconds: Window size in seconds
    
    Returns:
        Tuple of (min_timestamp, max_timestamp)
    """
    half_window = window_seconds // 2
    return (
        reference_timestamp - half_window,
        reference_timestamp + half_window
    )


def get_time_buckets(
    start_time: datetime, 
    end_time: datetime, 
    bucket_size_minutes: int = 5
) -> list[Tuple[datetime, datetime]]:
    """
    Divide time range into buckets for aggregation
    
    Args:
        start_time: Start of the time range
        end_time: End of the time range
        bucket_size_minutes: Size of each bucket in minutes
    
    Returns:
        List of (bucket_start, bucket_end) tuples
    """
    buckets = []
    current_time = start_time
    bucket_delta = timedelta(minutes=bucket_size_minutes)
    
    while current_time < end_time:
        bucket_end = min(current_time + bucket_delta, end_time)
        buckets.append((current_time, bucket_end))
        current_time = bucket_end
    
    return buckets


def get_retention_cutoff_timestamp(retention_days: int = 30) -> int:
    """
    Get timestamp for data retention cutoff
    
    Args:
        retention_days: Number of days to retain data
    
    Returns:
        Timestamp before which data should be deleted
    """
    cutoff_time = get_current_utc_datetime() - timedelta(days=retention_days)
    return datetime_to_timestamp(cutoff_time)


class TimeWindowCalculator:
    """Utility class for calculating various time windows"""
    
    def __init__(self, base_time: Optional[datetime] = None):
        self.base_time = base_time or get_current_utc_datetime()
    
    def last_minutes(self, minutes: int) -> Tuple[datetime, datetime]:
        """Get time window for last N minutes"""
        end_time = self.base_time
        start_time = end_time - timedelta(minutes=minutes)
        return start_time, end_time
    
    def last_hours(self, hours: int) -> Tuple[datetime, datetime]:
        """Get time window for last N hours"""
        end_time = self.base_time
        start_time = end_time - timedelta(hours=hours)
        return start_time, end_time
    
    def last_days(self, days: int) -> Tuple[datetime, datetime]:
        """Get time window for last N days"""
        end_time = self.base_time
        start_time = end_time - timedelta(days=days)
        return start_time, end_time
    
    def current_hour(self) -> Tuple[datetime, datetime]:
        """Get current hour window"""
        start_time = self.base_time.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        return start_time, end_time
    
    def current_day(self) -> Tuple[datetime, datetime]:
        """Get current day window"""
        start_time = self.base_time.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)
        return start_time, end_time


if __name__ == "__main__":
    # Example usage and testing
    print("=== Time Utilities Testing ===")
    
    # Current time functions
    print(f"Current timestamp: {get_current_timestamp()}")
    print(f"Current timestamp (ms): {get_current_timestamp_ms()}")
    print(f"Current UTC datetime: {get_current_utc_datetime()}")
    print(f"Current ISO string: {get_current_iso_string()}")
    
    # Time window calculations
    calc = TimeWindowCalculator()
    start, end = calc.last_minutes(5)
    print(f"Last 5 minutes: {start} to {end}")
    
    # Correlation window testing
    ref_time = get_current_timestamp()
    is_within = is_within_time_window(ref_time, ref_time + 5, 10)
    print(f"Timestamps within 10s window: {is_within}")
    
    # Format testing
    duration_str = format_duration(125.5)
    print(f"Duration formatting: {duration_str}")
    
    print("✅ Time utilities testing completed successfully!")