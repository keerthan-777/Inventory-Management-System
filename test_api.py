
import urllib.request
import urllib.error
import json

url = "http://127.0.0.1:5000/api/products"

# First, create a valid product
data = {
    "name": "Duplicate Test Product",
    "sku": "DUPLICATE001",
    "category": "Testing",
    "quantity": 10,
    "purchase_price": 100,
    "selling_price": 150
}

def send_request(data):
    request = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        response = urllib.request.urlopen(request)
        print("Status:", response.status)
        print(response.read().decode())
    except urllib.error.HTTPError as error:
        print("Status:", error.code)
        print(error.read().decode())

print("First request:")
send_request(data)

print("\nSecond request with the same SKU:")
send_request(data)
