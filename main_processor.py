"""
Main Processor - Enhanced orchestration engine for monitoring platform
with configuration management, robust error handling, and performance monitoring
"""

import mysql.connector
from mysql.connector import pooling
import time
import sys
import os
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_config
from shared.logger import get_logger
from shared.time_utils import (
    get_current_timestamp, 
    get_time_window_timestamps,
    format_duration
)
from correlator.correlate import correlate
from anomaly_detector.detect import detect_anomalies
from alerting_system.alert import send_alert

def get_mysql_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        return conn
    except mysql.connector.Error as err:
        print(f"MySQL Connection Error: {err}")
        return None

def fetch_recent_data(conn):
    """Fetches recent data from hyphenmon_metrics and zabbix_items tables."""
    cursor = conn.cursor(dictionary=True)
    hyphenmon_records = []
    zabbix_records = []

    try:
        # Fetch hyphenmon data
        query_hyphenmon = f"""
        SELECT timestamp, response_time_ms, error_rate 
        FROM hyphenmon_metrics 
        WHERE recorded_at >= NOW() - INTERVAL {DATA_FETCH_INTERVAL_MINUTES} MINUTE 
        ORDER BY timestamp DESC
        """
        cursor.execute(query_hyphenmon)
        hyphenmon_records = cursor.fetchall()
        print(f"Fetched {len(hyphenmon_records)} records from hyphenmon_metrics.")

        # Fetch Zabbix data
        query_zabbix = f"""
        SELECT itemid, name, lastvalue, lastclock, hostid
        FROM zabbix_items 
        WHERE recorded_at >= NOW() - INTERVAL {DATA_FETCH_INTERVAL_MINUTES} MINUTE 
        ORDER BY lastclock DESC
        """
        cursor.execute(query_zabbix)
        zabbix_records = cursor.fetchall()
        print(f"Fetched {len(zabbix_records)} records from zabbix_items.")

    except mysql.connector.Error as err:
        print(f"MySQL Query Error: {err}")
    finally:
        cursor.close()
    return zabbix_records, hyphenmon_records

def process_data():
    """Main function to orchestrate data processing, correlation, and alerting."""
    print(f"Starting data processing cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}...")
    conn = get_mysql_connection()
    if not conn:
        print("Could not connect to MySQL. Aborting processing cycle.")
        return

    try:
        zabbix_data_list, hyphenmon_data_list = fetch_recent_data(conn)

        if not hyphenmon_data_list:
            print("No recent hyphenmon data to process.")
            return

        # Correlation logic:
        # Iterate through hyphenmon data and try to find corresponding zabbix data.
        # The `correlate` function expects one hyphenmon_data item (dict) 
        # and a list of zabbix_data items (list of dicts) to search within.
        # For simplicity, we'll try to correlate each hyphenmon item with all recent zabbix items.
        # A more optimized approach might pre-filter zabbix items based on hostid or other criteria.

        successful_correlations = 0
        for h_data in hyphenmon_data_list:
            # The correlate function expects zabbix_data as a list of dicts, 
            # and hyphenmon_data as a single dict.
            # It will iterate through the zabbix_data_list to find a match.
            print(f"Attempting to correlate Hyphenmon data (ts: {h_data.get('timestamp')}) with {len(zabbix_data_list)} Zabbix records.")
            
            correlated_output = correlate(zabbix_data_list, h_data) # Pass the full list of recent Zabbix data

            if correlated_output:
                successful_correlations += 1
                print(f"  Correlation successful: {correlated_output}")
                
                # Anomaly Detection
                # The detect_anomalies function expects the direct output of correlate
                alerts = detect_anomalies(correlated_output) 
                if alerts:
                    for alert_message in alerts:
                        print(f"    Anomaly detected: {alert_message}")
                        # Send alert (uncomment and ensure alerting_system.alert is configured)
                        # try:
                        #     send_alert("Monitoring Platform Alert", alert_message)
                        #     print(f"      Alert sent: {alert_message}")
                        # except Exception as e:
                        #     print(f"      Failed to send alert: {e}")
                else:
                    print("    No anomalies detected in this correlated data.")
            # else:
            #     print(f"  No correlation found for Hyphenmon data (ts: {h_data.get('timestamp')}) with the given Zabbix data.")
        
        if successful_correlations == 0 and hyphenmon_data_list:
             print("No successful correlations in this cycle despite having Hyphenmon data.")


    except Exception as e:
        print(f"An error occurred during data processing: {e}")
    finally:
        if conn and conn.is_connected():
            conn.close()
            print("MySQL connection closed.")
    print(f"Data processing cycle finished at {time.strftime('%Y-%m-%d %H:%M:%S')}.")

if __name__ == "__main__":
    # You would typically run this script periodically (e.g., via cron or a scheduler)
    # For testing, you can run it directly.
    # Ensure you've configured MYSQL_* and SMTP_* constants at the top of this file.
    
    # Update alerting_system.alert.py with actual SMTP details if you uncomment alert sending
    # For now, send_alert is commented out in process_data to prevent errors if not configured.
    
    print("Reminder: Configure MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE at the top of this script.")
    print("If you intend to send email alerts, also configure SMTP_* constants and uncomment the send_alert call.")
    process_data()
