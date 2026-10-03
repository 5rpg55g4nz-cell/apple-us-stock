import requests

PART_NUMBER = "MJW64LL/A"
ZIP_CODE = "97205"

TARGET_STORES = {
    "Pioneer Place",
    "Washington Square",
    "Bridgeport Village",
}

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

response.raise_for_status()
data = response.json()

stores = data.get("body", {}).get("stores", [])

print(f"Apple US Stock Checker")
print(f"Product: {PART_NUMBER}")
print("=" * 45)

available_stores = []

for store in stores:
    name = store.get("storeName", "")

    if name not in TARGET_STORES:
        continue

    availability = (
        store.get("partsAvailability", {})
        .get(PART_NUMBER, {})
    )

    pickup = availability.get("pickupDisplay", "unknown")

    if pickup == "available":
        print(f"🟢 {name}: AVAILABLE")
        available_stores.append(name)
    else:
        print(f"🔴 {name}: UNAVAILABLE")

print("=" * 45)

if available_stores:
    print("🚨 STOCK FOUND!")
    print("Available at:")
    for store_name in available_stores:
        print(f" - {store_name}")
else:
    print("No stock in Oregon.")
