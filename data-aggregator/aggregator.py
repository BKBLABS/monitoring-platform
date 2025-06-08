import requests
from zabbix_client import ZabbixClient


def fetch_hyphenmon():
    return requests.get("http://localhost:5001/metrics").json()


def aggregate():
    zabbix = ZabbixClient("http://192.168.1.7/api_jsonrpc.php", "Admin", "zabbix")
    z_data = zabbix.get_items("10105")  
    h_data = fetch_hyphenmon()
    return {"zabbix": z_data, "hyphenmon": h_data}


if __name__ == "__main__":
    print(aggregate())
