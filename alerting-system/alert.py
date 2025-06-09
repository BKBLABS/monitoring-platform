"""
Enhanced Alerting System - Advanced notification service with
multiple channels, configuration management, and intelligent routing
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Add project root to path for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from config.settings import get_config
from shared.logger import get_logger
from shared.time_utils import get_current_timestamp, format_duration


class AlertSeverity(Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AlertChannel(Enum):
    """Available notification channels."""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"


@dataclass
class Alert:
    """Alert data structure."""
    title: str
    message: str
    severity: AlertSeverity
    source: str
    timestamp: float
    metadata: Dict[str, Any] = None
    alert_id: str = None

    def __post_init__(self):
        if self.alert_id is None:
            self.alert_id = f"{self.source}_{int(self.timestamp)}_{hash(self.title)}"
        if self.metadata is None:
            self.metadata = {}


class AlertingSystem:
    """Enhanced alerting system with multiple notification channels."""

    def __init__(self, config=None):
        self.logger = get_logger('alerting-system', 'alerting')

        # Load configuration
        if config is None:
            config = get_config()

        self.config = config
        self.alert_config = config.get_alerting_config()

        # Track sent alerts to prevent spam
        self.sent_alerts = {}
        self.rate_limit_window = 300  # 5 minutes

        self.logger.info(
            "Alerting system initialized",
            email_enabled=self.alert_config.email_enabled,
            slack_enabled=self.alert_config.slack_enabled,
            webhook_enabled=self.alert_config.webhook_enabled
        )

    def send_alert(self, alert: Alert, channels: List[AlertChannel] = None) -> Dict[str, Any]:
        """Send alert through specified channels.

        Args:
            alert: Alert object to send
            channels: List of channels to use (default: all configured)

        Returns:
            Dictionary with delivery results per channel
        """
        # Check rate limiting
        if self._is_rate_limited(alert):
            self.logger.warning(
                "Alert rate limited",
                alert_id=alert.alert_id,
                title=alert.title,
                source=alert.source
            )
            return {'rate_limited': True, 'channels': {}}

        # Determine channels to use
        if channels is None:
            channels = self._get_default_channels(alert.severity)

        results = {
            'alert_id': alert.alert_id,
            'timestamp': alert.timestamp,
            'channels': {},
            'success': False,
            'total_sent': 0
        }

        # Send through each channel
        for channel in channels:
            try:
                channel_result = self._send_to_channel(alert, channel)
                results['channels'][channel.value] = channel_result

                if channel_result.get('success', False):
                    results['total_sent'] += 1

            except Exception as e:
                self.logger.error(
                    "Failed to send alert through channel",
                    channel=channel.value,
                    alert_id=alert.alert_id,
                    error=str(e),
                    exc_info=True
                )
                results['channels'][channel.value] = {
                    'success': False,
                    'error': str(e)
                }

        results['success'] = results['total_sent'] > 0

        # Track sent alert
        if results['success']:
            self._track_sent_alert(alert)

        self.logger.info(
            "Alert sending completed",
            alert_id=alert.alert_id,
            severity=alert.severity.value,
            channels_attempted=len(channels),
            channels_successful=results['total_sent'],
            success=results['success']
        )

        return results

    def _send_to_channel(self, alert: Alert, channel: AlertChannel) -> Dict[str, Any]:
        """Send alert to specific channel."""
        if channel == AlertChannel.EMAIL:
            return self._send_email(alert)
        elif channel == AlertChannel.SLACK:
            return self._send_slack(alert)
        elif channel == AlertChannel.WEBHOOK:
            return self._send_webhook(alert)
        elif channel == AlertChannel.SMS:
            return self._send_sms(alert)
        else:
            return {'success': False, 'error': f'Unknown channel: {channel}'}

    def _send_email(self, alert: Alert) -> Dict[str, Any]:
        """Send alert via email."""
        if not self.alert_config.email_enabled:
            return {'success': False, 'error': 'Email not configured'}

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.alert_config.email_from
            msg['To'] = ', '.join(self.alert_config.email_recipients)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"

            # Create HTML body
            html_body = self._create_email_body(alert)
            msg.attach(MIMEText(html_body, 'html'))

            # Send email
            with smtplib.SMTP(self.alert_config.smtp_host, self.alert_config.smtp_port) as server:
                if self.alert_config.smtp_use_tls:
                    server.starttls()

                if self.alert_config.smtp_username and self.alert_config.smtp_password:
                    server.login(self.alert_config.smtp_username, self.alert_config.smtp_password)

                server.send_message(msg)

            return {
                'success': True,
                'recipients': len(self.alert_config.email_recipients),
                'message': 'Email sent successfully'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_slack(self, alert: Alert) -> Dict[str, Any]:
        """Send alert to Slack."""
        if not self.alert_config.slack_enabled:
            return {'success': False, 'error': 'Slack not configured'}

        try:
            payload = self._create_slack_payload(alert)
            response = requests.post(
                self.alert_config.slack_webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            return {
                'success': True,
                'response_code': response.status_code,
                'message': 'Slack message sent successfully'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_webhook(self, alert: Alert) -> Dict[str, Any]:
        """Send alert to webhook endpoint."""
        if not self.alert_config.webhook_enabled:
            return {'success': False, 'error': 'Webhook not configured'}

        try:
            payload = self._create_webhook_payload(alert)
            response = requests.post(
                self.alert_config.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()

            return {
                'success': True,
                'response_code': response.status_code,
                'message': 'Webhook sent successfully'
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_sms(self, alert: Alert) -> Dict[str, Any]:
        """Send alert via SMS (placeholder for SMS provider integration)."""
        # This would integrate with SMS providers like Twilio, AWS SNS, etc.
        return {
            'success': False,
            'error': 'SMS integration not implemented'
        }

    def _create_email_body(self, alert: Alert) -> str:
        """Create HTML email body."""
        severity_colors = {
            AlertSeverity.CRITICAL: '#dc3545',
            AlertSeverity.HIGH: '#fd7e14',
            AlertSeverity.MEDIUM: '#ffc107',
            AlertSeverity.LOW: '#28a745',
            AlertSeverity.INFO: '#17a2b8'
        }

        color = severity_colors.get(alert.severity, '#6c757d')
        timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(alert.timestamp))

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f8f9fa;">
            <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="background: {color}; color: white; padding: 20px;">
                    <h1 style="margin: 0; font-size: 24px;">🚨 Alert: {alert.title}</h1>
                    <p style="margin: 5px 0 0 0; opacity: 0.9;">Severity: {alert.severity.value.upper()}</p>
                </div>
                <div style="padding: 20px;">
                    <h2 style="color: #333; margin-top: 0;">Alert Details</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold; width: 120px;">Source:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{alert.source}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold;">Time:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6;">{timestamp_str}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-weight: bold;">Alert ID:</td>
                            <td style="padding: 8px; border-bottom: 1px solid #dee2e6; font-family: monospace;">{alert.alert_id}</td>
                        </tr>
                    </table>
                    <h3 style="color: #333; margin-top: 20px;">Message</h3>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 4px; border-left: 4px solid {color};">
                        {alert.message}
                    </div>
        """

        if alert.metadata:
            html += """
                    <h3 style="color: #333; margin-top: 20px;">Additional Information</h3>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 4px;">
            """
            for key, value in alert.metadata.items():
                html += f"<p style='margin: 5px 0;'><strong>{key}:</strong> {value}</p>"
            html += "</div>"

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def _create_slack_payload(self, alert: Alert) -> Dict[str, Any]:
        """Create Slack message payload."""
        severity_emojis = {
            AlertSeverity.CRITICAL: '🔴',
            AlertSeverity.HIGH: '🟠',
            AlertSeverity.MEDIUM: '🟡',
            AlertSeverity.LOW: '🟢',
            AlertSeverity.INFO: '🔵'
        }

        severity_colors = {
            AlertSeverity.CRITICAL: 'danger',
            AlertSeverity.HIGH: 'warning',
            AlertSeverity.MEDIUM: 'warning',
            AlertSeverity.LOW: 'good',
            AlertSeverity.INFO: '#17a2b8'
        }

        emoji = severity_emojis.get(alert.severity, '⚪')
        color = severity_colors.get(alert.severity, '#6c757d')
        timestamp_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(alert.timestamp))

        fields = [
            {
                "title": "Source",
                "value": alert.source,
                "short": True
            },
            {
                "title": "Severity",
                "value": alert.severity.value.upper(),
                "short": True
            },
            {
                "title": "Time",
                "value": timestamp_str,
                "short": True
            },
            {
                "title": "Alert ID",
                "value": f"`{alert.alert_id}`",
                "short": True
            }
        ]

        # Add metadata as fields
        if alert.metadata:
            for key, value in alert.metadata.items():
                fields.append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })

        return {
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} {alert.title}",
                    "text": alert.message,
                    "fields": fields,
                    "ts": int(alert.timestamp)
                }
            ]
        }

    def _create_webhook_payload(self, alert: Alert) -> Dict[str, Any]:
        """Create generic webhook payload."""
        return {
            "alert_id": alert.alert_id,
            "title": alert.title,
            "message": alert.message,
            "severity": alert.severity.value,
            "source": alert.source,
            "timestamp": alert.timestamp,
            "metadata": alert.metadata
        }

    def _get_default_channels(self, severity: AlertSeverity) -> List[AlertChannel]:
        """Get default channels based on severity."""
        channels = []

        # Email for all severities if enabled
        if self.alert_config.email_enabled:
            channels.append(AlertChannel.EMAIL)

        # Slack for medium and above if enabled
        if (self.alert_config.slack_enabled and 
            severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH, AlertSeverity.MEDIUM]):
            channels.append(AlertChannel.SLACK)

        # Webhook for high and critical if enabled
        if (self.alert_config.webhook_enabled and 
            severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]):
            channels.append(AlertChannel.WEBHOOK)

        return channels

    def _is_rate_limited(self, alert: Alert) -> bool:
        """Check if alert is rate limited."""
        current_time = time.time()
        alert_key = f"{alert.source}_{alert.title}"

        if alert_key in self.sent_alerts:
            last_sent = self.sent_alerts[alert_key]
            if current_time - last_sent < self.rate_limit_window:
                return True

        return False

    def _track_sent_alert(self, alert: Alert):
        """Track sent alert for rate limiting."""
        alert_key = f"{alert.source}_{alert.title}"
        self.sent_alerts[alert_key] = time.time()

        # Clean up old entries
        current_time = time.time()
        self.sent_alerts = {
            k: v for k, v in self.sent_alerts.items()
            if current_time - v < self.rate_limit_window * 2
        }

    def create_system_alert(self, title: str, message: str, 
                          severity: AlertSeverity = AlertSeverity.MEDIUM,
                          source: str = "monitoring-platform", 
                          metadata: Dict[str, Any] = None) -> Alert:
        """Create a system alert with current timestamp."""
        return Alert(
            title=title,
            message=message,
            severity=severity,
            source=source,
            timestamp=get_current_timestamp(),
            metadata=metadata or {}
        )

    def send_test_alert(self) -> Dict[str, Any]:
        """Send a test alert to verify configuration."""
        test_alert = self.create_system_alert(
            title="Test Alert - System Check",
            message="This is a test alert to verify the alerting system configuration.",
            severity=AlertSeverity.INFO,
            metadata={
                "test": True,
                "system": "alerting-system",
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        )

        return self.send_alert(test_alert)


def main():
    """CLI entry point for testing the alerting system."""
    try:
        print("🚀 Enhanced Alerting System - Starting...")

        # Initialize alerting system
        alerting = AlertingSystem()

        # Check configuration
        config_status = []
        if alerting.alert_config.email_enabled:
            config_status.append("✅ Email notifications enabled")
        else:
            config_status.append("❌ Email notifications disabled")

        if alerting.alert_config.slack_enabled:
            config_status.append("✅ Slack notifications enabled")
        else:
            config_status.append("❌ Slack notifications disabled")

        if alerting.alert_config.webhook_enabled:
            config_status.append("✅ Webhook notifications enabled")
        else:
            config_status.append("❌ Webhook notifications disabled")

        print("\n📋 Configuration Status:")
        for status in config_status:
            print(f"   {status}")

        # Send test alert
        print("\n🔔 Sending test alert...")
        results = alerting.send_test_alert()

        print("\n📊 Test Alert Results:")
        print(f"   • Success: {results['success']}")
        print(f"   • Alert ID: {results['alert_id']}")
        print(f"   • Channels attempted: {len(results['channels'])}")
        print(f"   • Channels successful: {results['total_sent']}")

        if results['channels']:
            print("\n📡 Channel Results:")
            for channel, result in results['channels'].items():
                status = "✅" if result.get('success', False) else "❌"
                print(f"   {status} {channel}: {result.get('message', result.get('error', 'Unknown'))}")

        print("\n💡 To create custom alerts, use alerting.create_system_alert()")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
