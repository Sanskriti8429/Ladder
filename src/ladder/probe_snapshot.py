import json
import urllib.request

URL = "https://api.binance.com/api/v3/depth?symbol=BTCUSDT&limit=1000"

with urllib.request.urlopen(URL) as resp:
    snap = json.loads(resp.read())

print(list(snap.keys()))
print("lastUpdateId:", snap["lastUpdateId"])
print("bids:", len(snap["bids"]), "asks:", len(snap["asks"]))
print("first bid:", snap["bids"][0], "last bid:", snap["bids"][-1])
print("first ask:", snap["asks"][0], "last ask:", snap["asks"][-1])