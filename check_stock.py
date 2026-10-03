import requests

PART_NUMBER = "MJW64LL/A"
ZIP_CODE = "97205"  # Portland, Oregon

url = "https://www.apple.com/shop/retail/pickup-message"

params = {
    "pl": "true",
    "parts.0": PART_NUMBER,
    "location": ZIP_CODE,
}

headers = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.apple.com/shop/",
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=20
)

print("HTTP Status:", response.status_code)
print("Request URL:", response.url)

response.raise_for_status()

data = response.json()

stores = data.get("body", {}).get("stores", [])

print(f"Stores returned: {len(stores)}")
print("=" * 50)

for store in stores:
    name = store.get("storeName", "Unknown Store")
    state = store.get("state", "")

    availability = store.get("partsAvailability", {}).get(
        PART_NUMBER, {}
    )

    pickup = availability.get("pickupDisplay", "unknown")

    print(f"{name} | {state} | {pickup}")
