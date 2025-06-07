import requests


class ZabbixClient:
    def __init__(self, url, user, password):
        self.url = url
        self.auth = self.login(user, password)

    def login(self, user, password):
        payload = {
            "jsonrpc": "2.0",
            "method": "user.login",
            "params": {"user": user, "password": password},
            "id": 1,
            "auth": None,
        }
        res = requests.post(self.url, json=payload).json()
        return res["result"]

    def get_items(self, hostid):
        payload = {
            "jsonrpc": "2.0",
            "method": "item.get",
            "params": {"output": "extend", "hostids": hostid},
            "auth": self.auth,
            "id": 2,
        }
        res = requests.post(self.url, json=payload).json()
        return res["result"]
