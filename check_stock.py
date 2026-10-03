import os
import requests

PART_NUMBER = "MJW64LL/A"
ZIP_CODE = "97205"

TARGET_STORES = {
    "Pioneer Place",
    "Washington Square",
    "Bridgeport Village",
}

APPLE_URL = "https://www.apple.com/shop/retail/pickup-message"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

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
    APPLE_URL,
    params=params,
    headers=headers,
    timeout=20
)

response.raise_for_status()
data = response.json()

stores = data.get("body", {}).get("stores", [])

available_stores = []

print("Apple US Stock Checker")
print(f"Product: {PART_NUMBER}")
print("=" * 45)

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

    if not NTFY_TOPIC:
        raise RuntimeError("NTFY_TOPIC is not configured")

    store_list = ", ".join(available_stores)

    notification = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=(
            f"MJW64LL/A is AVAILABLE!\n"
            f"Store: {store_list}\n"
            f"Check Apple Store now."
        ).encode("utf-8"),
        headers={
            "Title": "Apple US Stock Found!",
            "Priority": "urgent",
            "Tags": "apple,rotating_light",
        },
        timeout=20,
    )

    notification.raise_for_status()

else:
    print("No stock in Oregon. No notification sent.")
    
