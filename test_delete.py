
import urllib.request
import urllib.error

url = "http://127.0.0.1:5000/api/products/1"

request = urllib.request.Request(
    url,
    method="DELETE"
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
