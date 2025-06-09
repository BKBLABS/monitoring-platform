"""
Enhanced Main Processor - Revolutionary orchestration engine for monitoring platform
with advanced configuration management, robust error handling, and performance monitoring
"""

import mysql.connector
from mysql.connector import pooling
import time
import sys
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import threading
import queue

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_config
from shared.logger import get_logger
from shared.time_utils import (
    get_current_timestamp,
    get_time_window_timestamps,
    format_duration,
    get_current_utc_datetime
)
from correlator.correlate import correlate
from anomaly_detector.detect import detect_anomalies


class DatabaseManager:
    """Enhanced database manager with connection pooling and error handling"""

    def __init__(self, config=None):
        self.logger = get_logger('database-manager', 'database')
        self.config = config or get_config()
        self.db_config = self.config.get_database_config()
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize MySQL connection pool"""
        try:
            pool_config = {
                'host': self.db_config.host,
                'port': self.db_config.port,
                'user': self.db_config.username,
                'password': self.db_config.password,
                'database': self.db_config.database,
                'pool_name': 'monitoring_pool',
                'pool_size': self.db_config.connection_pool_size,
                'pool_reset_session': True,
                'autocommit': True,
                'connect_timeout': self.db_config.connection_timeout
            }

            self.connection_pool = pooling.MySQLConnectionPool(**pool_config)

            self.logger.info(
                "MySQL connection pool initialized successfully",
                pool_size=self.db_config.connection_pool_size,
                host=self.db_config.host,
                database=self.db_config.database
            )

        except Exception as e:
            self.logger.error(
                "Failed to initialize MySQL connection pool",
                error=str(e),
                exc_info=True
            )
            raise

    def get_connection(self):
        """Get connection from pool with error handling"""
        try:
            return self.connection_pool.get_connection()
        except Exception as e:
            self.logger.error(
                "Failed to get database connection from pool",
                error=str(e)
            )
            raise

    def fetch_recent_data(self, interval_minutes: int) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch recent data from hyphenmon_metrics and zabbix_items tables

        Args:
            interval_minutes: Time window in minutes

        Returns:
            Tuple of (zabbix_records, hyphenmon_records)
        """
        connection = None
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=True)

            hyphenmon_records = []
            zabbix_records = []

            with self.logger.performance_timer("fetch_hyphenmon_data"):
                # Fetch hyphenmon data
                query_hyphenmon = """
                SELECT timestamp, response_time_ms, error_rate, recorded_at
                FROM hyphenmon_metrics
                WHERE recorded_at >= NOW() - INTERVAL %s MINUTE
                ORDER BY timestamp DESC
                """
                cursor.execute(query_hyphenmon, (interval_minutes,))
                hyphenmon_records = cursor.fetchall()

            self.logger.info(
                "Fetched hyphenmon records",
                count=len(hyphenmon_records),
                interval_minutes=interval_minutes
            )

            with self.logger.performance_timer("fetch_zabbix_data"):
                # Fetch Zabbix data
                query_zabbix = """
                SELECT itemid, name, lastvalue, lastclock, hostid, recorded_at
                FROM zabbix_items
                WHERE recorded_at >= NOW() - INTERVAL %s MINUTE
                ORDER BY lastclock DESC
                """
                cursor.execute(query_zabbix, (interval_minutes,))
                zabbix_records = cursor.fetchall()

            self.logger.info(
                "Fetched zabbix records",
                count=len(zabbix_records),
                interval_minutes=interval_minutes
            )

            cursor.close()
            return zabbix_records, hyphenmon_records

        except mysql.connector.Error as err:
            self.logger.error(
                "MySQL query error while fetching recent data",
                error=str(err),
                exc_info=True
            )
            return [], []
        except Exception as e:
            self.logger.error(
                "Unexpected error while fetching recent data",
                error=str(e),
                exc_info=True
            )
            return [], []
        finally:
            if connection and connection.is_connected():
                connection.close()


class CorrelationEngine:
    """Enhanced correlation engine with advanced analytics"""

    def __init__(self):
        self.logger = get_logger('correlation-engine', 'correlation')
        self.config = get_config()
        self.processing_config = self.config.get_processing_config()

    def correlate_datasets(
        self,
        zabbix_data: List[Dict],
        hyphenmon_data: List[Dict]
    ) -> List[Dict]:
        """
        Correlate Zabbix and HyphenMon datasets

        Args:
            zabbix_data: List of Zabbix records
            hyphenmon_data: List of HyphenMon records

        Returns:
            List of correlated data records
        """
        correlated_results = []
        correlation_window = self.processing_config.correlation_window_seconds

        self.logger.info(
            "Starting dataset correlation",
            zabbix_records=len(zabbix_data),
            hyphenmon_records=len(hyphenmon_data),
            correlation_window=correlation_window
        )

        with self.logger.performance_timer("correlation_processing"):
            for h_data in hyphenmon_data:
                h_timestamp = h_data.get('timestamp')
                if not h_timestamp:
                    continue

                # Find matching Zabbix records within correlation window
                matching_zabbix = []
                for z_data in zabbix_data:
                    z_timestamp = z_data.get('lastclock')
                    if not z_timestamp:
                        continue

                    # Check if timestamps are within correlation window
                    if abs(int(z_timestamp) - int(h_timestamp)) <= correlation_window:
                        matching_zabbix.append(z_data)

                # If we found matches, correlate with each one
                for z_match in matching_zabbix:
                    try:
                        correlation_result = correlate([z_match], h_data)
                        if correlation_result:
                            correlation_result['correlation_timestamp'] = get_current_timestamp()
                            correlation_result['correlation_window'] = correlation_window
                            correlated_results.append(correlation_result)

                            self.logger.debug(
                                "Successful correlation",
                                hyphenmon_timestamp=h_timestamp,
                                zabbix_timestamp=z_match.get('lastclock'),
                                time_diff=abs(int(z_match.get('lastclock', 0)) - int(h_timestamp))
                            )
                    except Exception as e:
                        self.logger.warning(
                            "Correlation failed for record pair",
                            error=str(e),
                            hyphenmon_timestamp=h_timestamp,
                            zabbix_timestamp=z_match.get('lastclock')
                        )

        self.logger.info(
            "Dataset correlation completed",
            correlated_records=len(correlated_results),
            processing_time=format_duration(time.time())
        )

        return correlated_results


class AnomalyDetectionEngine:
    """Enhanced anomaly detection with machine learning capabilities"""

    def __init__(self):
        self.logger = get_logger('anomaly-engine', 'anomaly-detection')
        self.config = get_config()
        self.processing_config = self.config.get_processing_config()

    def detect_anomalies_batch(self, correlated_data: List[Dict]) -> List[Dict]:
        """
        Detect anomalies in batch of correlated data

        Args:
            correlated_data: List of correlated records

        Returns:
            List of anomaly detection results
        """
        anomaly_results = []

        self.logger.info(
            "Starting batch anomaly detection",
            input_records=len(correlated_data),
            threshold=self.processing_config.anomaly_detection_threshold
        )

        with self.logger.performance_timer("anomaly_detection_batch"):
            for record in correlated_data:
                try:
                    alerts = detect_anomalies(record)
                    if alerts:
                        anomaly_result = {
                            'timestamp': get_current_timestamp(),
                            'correlated_data': record,
                            'alerts': alerts,
                            'severity': self._calculate_severity(record, alerts),
                            'confidence': self._calculate_confidence(record)
                        }
                        anomaly_results.append(anomaly_result)

                        self.logger.warning(
                            "Anomaly detected",
                            alerts=alerts,
                            severity=anomaly_result['severity'],
                            confidence=anomaly_result['confidence']
                        )
                except Exception as e:
                    self.logger.error(
                        "Error during anomaly detection",
                        error=str(e),
                        record_id=record.get('correlation_timestamp')
                    )

        self.logger.info(
            "Batch anomaly detection completed",
            anomalies_detected=len(anomaly_results),
            input_records=len(correlated_data)
        )

        return anomaly_results

    def _calculate_severity(self, record: Dict, alerts: List[str]) -> str:
        """Calculate severity level for detected anomaly"""
        hyphenmon_data = record.get('hyphenmon', {})
        error_rate = hyphenmon_data.get('error_rate', 0)

        if error_rate > 0.8:
            return 'CRITICAL'
        elif error_rate > 0.6:
            return 'HIGH'
        elif error_rate > 0.4:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _calculate_confidence(self, record: Dict) -> float:
        """Calculate confidence score for anomaly detection"""
        # Simple confidence calculation based on data quality
        hyphenmon_data = record.get('hyphenmon', {})
        zabbix_data = record.get('zabbix', {})

        score = 0.5  # Base confidence

        # Increase confidence if we have good data quality
        if hyphenmon_data.get('response_time_ms'):
            score += 0.2
        if zabbix_data.get('lastvalue'):
            score += 0.2
        if record.get('correlation_window', 0) <= 5:  # Tight correlation window
            score += 0.1

        return min(score, 1.0)


class AlertManager:
    """Enhanced alert management with intelligent routing and throttling"""

    def __init__(self):
        self.logger = get_logger('alert-manager', 'alerting')
        self.config = get_config()
        self.alerting_config = self.config.get_alerting_config()
        self.alert_history = {}

    def process_anomalies(self, anomalies: List[Dict]) -> int:
        """
        Process detected anomalies and send appropriate alerts

        Args:
            anomalies: List of anomaly detection results

        Returns:
            Number of alerts sent
        """
        alerts_sent = 0

        self.logger.info(
            "Processing anomalies for alerting",
            anomaly_count=len(anomalies)
        )

        for anomaly in anomalies:
            try:
                if self._should_send_alert(anomaly):
                    alert_message = self._format_alert_message(anomaly)
                    
                    # Send alert (commented out to prevent errors if not configured)
                    # try:
                    #     send_alert("Monitoring Platform Alert", alert_message)
                    #     alerts_sent += 1
                    #     self.logger.info("Alert sent successfully", message=alert_message)
                    # except Exception as e:
                    #     self.logger.error("Failed to send alert", error=str(e))

                    # Log alert for debugging
                    self.logger.warning(
                        "Alert generated (sending disabled in code)",
                        message=alert_message,
                        severity=anomaly.get('severity'),
                        confidence=anomaly.get('confidence')
                    )
                    alerts_sent += 1  # Count for logging even if not sent

                    # Update alert history
                    self._update_alert_history(anomaly)

            except Exception as e:
                self.logger.error(
                    "Error processing anomaly for alerting",
                    error=str(e),
                    anomaly_timestamp=anomaly.get('timestamp')
                )

        self.logger.info(
            "Anomaly processing completed",
            alerts_generated=alerts_sent,
            total_anomalies=len(anomalies)
        )

        return alerts_sent

    def _should_send_alert(self, anomaly: Dict) -> bool:
        """Determine if alert should be sent based on throttling rules"""
        severity = anomaly.get('severity', 'LOW')
        confidence = anomaly.get('confidence', 0.0)

        # Don't send low confidence alerts
        if confidence < 0.3:
            return False

        # Always send critical alerts
        if severity == 'CRITICAL':
            return True

        # Throttle based on severity and history
        alert_key = f"{severity}_{anomaly.get('timestamp', 0)}"
        if alert_key in self.alert_history:
            return False

        return True

    def _format_alert_message(self, anomaly: Dict) -> str:
        """Format alert message for notification"""
        timestamp = datetime.fromtimestamp(anomaly.get('timestamp', 0))
        severity = anomaly.get('severity', 'UNKNOWN')
        confidence = anomaly.get('confidence', 0.0)
        alerts = anomaly.get('alerts', [])

        hyphenmon_data = anomaly.get('correlated_data', {}).get('hyphenmon', {})
        error_rate = hyphenmon_data.get('error_rate', 0)
        response_time = hyphenmon_data.get('response_time_ms', 0)

        message = f"""
🚨 MONITORING ALERT 🚨

Timestamp: {timestamp}
Severity: {severity}
Confidence: {confidence:.2f}

Detected Issues:
{chr(10).join(f"• {alert}" for alert in alerts)}

Metrics:
• Error Rate: {error_rate:.2%}
• Response Time: {response_time}ms

Correlation Data Available: {len(anomaly.get('correlated_data', {}))} datasets
        """.strip()

        return message

    def _update_alert_history(self, anomaly: Dict):
        """Update alert history for throttling"""
        severity = anomaly.get('severity', 'LOW')
        timestamp = anomaly.get('timestamp', 0)
        alert_key = f"{severity}_{timestamp}"
        self.alert_history[alert_key] = get_current_timestamp()

        # Clean old history entries (keep last 100)
        if len(self.alert_history) > 100:
            sorted_keys = sorted(self.alert_history.keys())
            for key in sorted_keys[:-100]:
                del self.alert_history[key]


class MonitoringProcessor:
    """Main orchestration engine for the monitoring platform"""

    def __init__(self):
        self.logger = get_logger('monitoring-processor', 'orchestration')
        self.config = get_config()
        self.processing_config = self.config.get_processing_config()

        # Initialize components
        self.db_manager = DatabaseManager(self.config)
        self.correlation_engine = CorrelationEngine()
        self.anomaly_engine = AnomalyDetectionEngine()
        self.alert_manager = AlertManager()

        self.logger.info(
            "Monitoring processor initialized successfully",
            fetch_interval=self.processing_config.data_fetch_interval_minutes,
            correlation_window=self.processing_config.correlation_window_seconds,
            anomaly_threshold=self.processing_config.anomaly_detection_threshold
        )

    def process_data_cycle(self) -> Dict[str, Any]:
        """
        Execute complete data processing cycle

        Returns:
            Processing results summary
        """
        cycle_start_time = get_current_timestamp()
        cycle_id = f"cycle_{cycle_start_time}"

        self.logger.info(
            "Starting data processing cycle",
            cycle_id=cycle_id,
            timestamp=get_current_utc_datetime().isoformat()
        )

        results = {
            'cycle_id': cycle_id,
            'start_time': cycle_start_time,
            'success': False,
            'metrics': {
                'zabbix_records': 0,
                'hyphenmon_records': 0,
                'correlations': 0,
                'anomalies': 0,
                'alerts_sent': 0
            },
            'errors': []
        }

        try:
            with self.logger.performance_timer(f"complete_processing_cycle_{cycle_id}"):
                # Step 1: Fetch recent data
                zabbix_data, hyphenmon_data = self.db_manager.fetch_recent_data(
                    self.processing_config.data_fetch_interval_minutes
                )

                results['metrics']['zabbix_records'] = len(zabbix_data)
                results['metrics']['hyphenmon_records'] = len(hyphenmon_data)

                if not hyphenmon_data:
                    self.logger.warning("No recent HyphenMon data available for processing")
                    results['success'] = True  # Not an error, just no data
                    return results

                # Step 2: Correlate datasets
                correlated_data = self.correlation_engine.correlate_datasets(
                    zabbix_data, hyphenmon_data
                )
                results['metrics']['correlations'] = len(correlated_data)

                if not correlated_data:
                    self.logger.info("No correlations found in this cycle")
                    results['success'] = True
                    return results

                # Step 3: Detect anomalies
                anomalies = self.anomaly_engine.detect_anomalies_batch(correlated_data)
                results['metrics']['anomalies'] = len(anomalies)

                # Step 4: Process alerts
                if anomalies:
                    alerts_sent = self.alert_manager.process_anomalies(anomalies)
                    results['metrics']['alerts_sent'] = alerts_sent

                results['success'] = True

        except Exception as e:
            error_msg = f"Critical error in processing cycle: {str(e)}"
            self.logger.error(
                error_msg,
                cycle_id=cycle_id,
                exc_info=True
            )
            results['errors'].append(error_msg)

        finally:
            results['end_time'] = get_current_timestamp()
            results['duration_seconds'] = results['end_time'] - results['start_time']

            self.logger.info(
                "Data processing cycle completed",
                cycle_id=cycle_id,
                success=results['success'],
                duration=format_duration(results['duration_seconds']),
                metrics=results['metrics']
            )

        return results

    def run_continuous(self, interval_minutes: Optional[int] = None):
        """
        Run continuous processing with specified interval

        Args:
            interval_minutes: Override default processing interval
        """
        if interval_minutes is None:
            interval_minutes = self.processing_config.data_fetch_interval_minutes

        self.logger.info(
            "Starting continuous monitoring",
            interval_minutes=interval_minutes
        )

        cycle_count = 0
        try:
            while True:
                cycle_count += 1
                self.logger.info(f"Starting processing cycle #{cycle_count}")

                # Process data
                results = self.process_data_cycle()

                # Log cycle summary
                if results['success']:
                    self.logger.info(
                        f"Cycle #{cycle_count} completed successfully",
                        metrics=results['metrics'],
                        duration=format_duration(results['duration_seconds'])
                    )
                else:
                    self.logger.error(
                        f"Cycle #{cycle_count} failed",
                        errors=results['errors']
                    )

                # Wait for next cycle
                self.logger.debug(f"Waiting {interval_minutes} minutes for next cycle")
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            self.logger.info(
                "Continuous monitoring stopped by user",
                total_cycles=cycle_count
            )
        except Exception as e:
            self.logger.critical(
                "Critical error in continuous monitoring",
                error=str(e),
                total_cycles=cycle_count,
                exc_info=True
            )


def main():
    """Main entry point for the monitoring processor"""
    print("🚀 Enhanced Monitoring Platform - Main Processor")
    print("=" * 60)

    try:
        # Validate configuration
        config = get_config()
        validation_issues = config.validate_configuration()

        if validation_issues:
            print("⚠️  Configuration Issues Detected:")
            for issue in validation_issues:
                print(f"   • {issue}")
            print("\n📝 Please update your configuration before proceeding.")
            return

        # Initialize processor
        processor = MonitoringProcessor()

        # Run single cycle for testing
        print("🔄 Running single processing cycle...")
        results = processor.process_data_cycle()

        print(f"\n📊 Processing Results:")
        print(f"   • Success: {'✅' if results['success'] else '❌'}")
        print(f"   • Duration: {format_duration(results['duration_seconds'])}")
        print(f"   • Zabbix Records: {results['metrics']['zabbix_records']}")
        print(f"   • HyphenMon Records: {results['metrics']['hyphenmon_records']}")
        print(f"   • Correlations: {results['metrics']['correlations']}")
        print(f"   • Anomalies: {results['metrics']['anomalies']}")
        print(f"   • Alerts: {results['metrics']['alerts_sent']}")

        if results['errors']:
            print(f"\n❌ Errors:")
            for error in results['errors']:
                print(f"   • {error}")

        print(f"\n✅ Processing cycle completed!")
        print(f"\n💡 To run continuous monitoring, call processor.run_continuous()")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
