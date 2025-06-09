"""
HyphenMon Connector - Enhanced REST API client with retry logic,
connection pooling, and comprehensive error handling
"""

import requests
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import get_config
from shared.logger import get_logger
from shared.time_utils import get_current_timestamp


class HyphenMonConnectionError(Exception):
    """Custom exception for HyphenMon connection issues"""
    pass


class HyphenMonClient:
    """Enhanced HyphenMon REST API client"""
    
    def __init__(self, config=None):
        self.logger = get_logger('hyphenmon-client', 'hyphenmon-connector')
        
        # Load configuration
        if config is None:
            config = get_config()
        
        self.hyphenmon_config = config.get_hyphenmon_config()
        self.base_url = self.hyphenmon_config.api_url
        self.timeout = self.hyphenmon_config.timeout
        self.retry_attempts = self.hyphenmon_config.retry_attempts
        
        # Setup HTTP session with retry strategy
        self.session = self._create_session()
        
        self.logger.info(
            "HyphenMon client initialized",
            base_url=self.base_url,
            timeout=self.timeout,
            retry_attempts=self.retry_attempts
        )
    
    def _create_session(self) -> requests.Session:
        """Create HTTP session with retry strategy and connection pooling"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default timeout
        session.timeout = self.timeout
        
        return session
    
    def _make_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request with error handling and logging
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            **kwargs: Additional request parameters
        
        Returns:
            Response data as dictionary
        
        Raises:
            HyphenMonConnectionError: On connection or HTTP errors
        """
        url = urljoin(self.base_url, endpoint)
        
        try:
            self.logger.debug(
                f"Making {method} request to HyphenMon",
                url=url,
                timeout=self.timeout
            )
            
            with self.logger.performance_timer(f"hyphenmon_request_{endpoint}"):
                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=self.timeout,
                    **kwargs
                )
                
                response.raise_for_status()
                
                # Try to parse JSON response
                try:
                    data = response.json()
                except ValueError as e:
                    self.logger.error(
                        "Failed to parse JSON response from HyphenMon",
                        url=url,
                        status_code=response.status_code,
                        content=response.text[:200]
                    )
                    raise HyphenMonConnectionError(f"Invalid JSON response: {e}")
                
                self.logger.debug(
                    "Successfully received response from HyphenMon",
                    url=url,
                    status_code=response.status_code,
                    response_size=len(response.content)
                )
                
                return data
        
        except requests.exceptions.Timeout:
            error_msg = f"Timeout connecting to HyphenMon at {url} (timeout: {self.timeout}s)"
            self.logger.error(error_msg, url=url, timeout=self.timeout)
            raise HyphenMonConnectionError(error_msg)
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error to HyphenMon at {url}: {str(e)}"
            self.logger.error(error_msg, url=url, error=str(e))
            raise HyphenMonConnectionError(error_msg)
        
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error from HyphenMon: {e.response.status_code} - {e.response.text}"
            self.logger.error(
                "HTTP error from HyphenMon",
                url=url,
                status_code=e.response.status_code,
                error_text=e.response.text[:200]
            )
            raise HyphenMonConnectionError(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error connecting to HyphenMon: {str(e)}"
            self.logger.error(error_msg, url=url, error=str(e), exc_info=True)
            raise HyphenMonConnectionError(error_msg)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics from HyphenMon
        
        Returns:
            Dictionary containing metrics data
        """
        try:
            metrics = self._make_request(self.hyphenmon_config.metrics_endpoint)
            
            # Add collection timestamp
            metrics['collected_at'] = get_current_timestamp()
            
            self.logger.info(
                "Successfully collected metrics from HyphenMon",
                timestamp=metrics.get('timestamp'),
                response_time=metrics.get('response_time_ms'),
                error_rate=metrics.get('error_rate')
            )
            
            return metrics
        
        except HyphenMonConnectionError:
            # Re-raise connection errors
            raise
        except Exception as e:
            error_msg = f"Failed to get metrics from HyphenMon: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise HyphenMonConnectionError(error_msg)
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status from HyphenMon
        
        Returns:
            Dictionary containing health status
        """
        try:
            health_data = self._make_request(self.hyphenmon_config.health_check_endpoint)
            
            self.logger.info(
                "HyphenMon health check completed",
                status=health_data.get('status', 'unknown')
            )
            
            return health_data
        
        except HyphenMonConnectionError:
            # Log but don't re-raise for health checks
            self.logger.warning("HyphenMon health check failed")
            return {
                'status': 'unhealthy',
                'error': 'Connection failed',
                'timestamp': get_current_timestamp()
            }
    
    def get_batch_metrics(self, count: int = 10, interval_seconds: int = 1) -> List[Dict[str, Any]]:
        """
        Collect multiple metric samples over time
        
        Args:
            count: Number of samples to collect
            interval_seconds: Interval between samples
        
        Returns:
            List of metric dictionaries
        """
        metrics_batch = []
        
        self.logger.info(
            "Starting batch metrics collection",
            sample_count=count,
            interval_seconds=interval_seconds
        )
        
        for i in range(count):
            try:
                metrics = self.get_metrics()
                metrics['batch_index'] = i
                metrics_batch.append(metrics)
                
                # Sleep between samples (except for the last one)
                if i < count - 1:
                    time.sleep(interval_seconds)
            
            except HyphenMonConnectionError as e:
                self.logger.warning(
                    f"Failed to collect metric sample {i+1}/{count}",
                    error=str(e)
                )
                # Continue with next sample
                continue
        
        self.logger.info(
            "Batch metrics collection completed",
            collected_samples=len(metrics_batch),
            requested_samples=count
        )
        
        return metrics_batch
    
    def validate_connection(self) -> bool:
        """
        Validate connection to HyphenMon
        
        Returns:
            True if connection is successful
        """
        try:
            self.logger.info("Validating HyphenMon connection")
            
            # Try health check first
            health = self.get_health_status()
            if health.get('status') == 'healthy':
                return True
            
            # Fallback to metrics endpoint
            self.get_metrics()
            return True
        
        except Exception as e:
            self.logger.error(
                "HyphenMon connection validation failed",
                error=str(e)
            )
            return False
    
    def close(self):
        """Close the HTTP session"""
        if self.session:
            self.session.close()
            self.logger.info("HyphenMon client session closed")


# Factory function for creating HyphenMon clients
def create_hyphenmon_client(config=None) -> HyphenMonClient:
    """Create a new HyphenMon client instance"""
    return HyphenMonClient(config=config)


if __name__ == "__main__":
    # Example usage and testing
    print("=== HyphenMon Connector Testing ===")
    
    try:
        client = create_hyphenmon_client()
        
        # Test connection validation
        is_connected = client.validate_connection()
        print(f"Connection validation: {'✅ Success' if is_connected else '❌ Failed'}")
        
        if is_connected:
            # Test single metrics collection
            metrics = client.get_metrics()
            print(f"Metrics collected: {metrics}")
            
            # Test health check
            health = client.get_health_status()
            print(f"Health status: {health}")
            
            # Test batch collection (small batch for testing)
            batch_metrics = client.get_batch_metrics(count=3, interval_seconds=1)
            print(f"Batch metrics collected: {len(batch_metrics)} samples")
        
        client.close()
        print("✅ HyphenMon connector testing completed successfully!")
    
    except Exception as e:
        print(f"❌ HyphenMon connector testing failed: {e}")
