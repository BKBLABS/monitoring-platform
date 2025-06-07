def detect_anomalies(correlated_data):
    alerts = []
    if correlated_data.get("hyphenmon", {}).get("error_rate", 0) > 0.5:
        alerts.append("High error rate in app!")
    return alerts
