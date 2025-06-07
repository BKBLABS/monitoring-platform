def correlate(zabbix_data, hyphenmon_data):
    z_ts = int(zabbix_data[0].get("lastclock", 0))
    h_ts = hyphenmon_data["timestamp"]
    if abs(z_ts - h_ts) <= 10:
        return {"zabbix": zabbix_data[0], "hyphenmon": hyphenmon_data}
    return {}
