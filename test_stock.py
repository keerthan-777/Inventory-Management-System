
import json
import urllib.request
import urllib.error

url = "http://127.0.0.1:5000/api/stock-movements"

data = {
    "product_id": 2,
    "movement_type": "in",
    "quantity": 10,
    "reason": "Received new stock"
}

request = urllib.request.Request(
    url,
    data=json.dumps(data).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(request) as response:
        print("Status:", response.status)
        print(response.read().decode())
except urllib.error.HTTPError as error:
    print("Status:", error.code)
    print(error.read().decode())
