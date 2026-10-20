
import urllib.request
import urllib.error
import json

url = "http://127.0.0.1:5000/api/products/1"

updates = {
    "quantity": 40,
    "selling_price": 700
}

request = urllib.request.Request(
    url,
    data=json.dumps(updates).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="PUT"
)

try:
    with urllib.request.urlopen(request) as response:
        print("Status:", response.status)
        print(response.read().decode("utf-8"))

except urllib.error.HTTPError as error:
    print("Status:", error.code)
    print(error.read().decode("utf-8"))

except urllib.error.URLError as error:
    print("Connection error:", error.reason)
