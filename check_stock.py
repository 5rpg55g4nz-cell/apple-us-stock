import requests
import json

PART_NUMBER = "MJW64LL/A"
ZIP_CODE = "97205"

url = "https://www.apple.com/shop/fulfillment-messages"

params = {
    "parts.0": PART_NUMBER,
    "location": ZIP_CODE,
}

headers = {
    "User-Agent": "Mozilla/5.0",
}

response = requests.get(url, params=params, headers=headers)

print("Status:", response.status_code)

try:
    data = response.json()
    print(json.dumps(data, indent=2))
except Exception:
    print(response.text)
