import os
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

APPLE_URL = "https://www.apple.com/shop/retail/pickup-message"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

# products.jsonを読み込む
with open("products.json", "r", encoding="utf-8") as file:
    config = json.load(file)

all_products = []

for product in config["products"]:

    part_number = product["partNumber"]
    zip_code = product["zipCode"]
    region = product["region"]
    target_stores = set(product["stores"])

    print("=" * 50)
    print(f"Checking: {part_number} / {region}")

    params = {
        "pl": "true",
        "parts.0": part_number,
        "location": zip_code,
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.apple.com/shop/",
    }

    response = requests.get(
        APPLE_URL,
        params=params,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    apple_stores = data.get("body", {}).get("stores", [])

    results = []
    available_stores = []

    for store in apple_stores:

        name = store.get("storeName", "")

        if name not in target_stores:
            continue

        availability = (
            store.get("partsAvailability", {})
            .get(part_number, {})
        )

        pickup = availability.get("pickupDisplay", "unknown")
        is_available = pickup == "available"

        results.append({
            "name": name,
            "available": is_available
        })

        if is_available:
            available_stores.append(name)

        symbol = "🟢" if is_available else "🔴"
        status = "AVAILABLE" if is_available else "UNAVAILABLE"

        print(f"{symbol} {name}: {status}")

    all_products.append({
        "partNumber": part_number,
        "name": product.get("name", part_number),
        "region": region,
        "stores": results
    })

    # 在庫があれば通知
    if available_stores and NTFY_TOPIC:

        store_list = ", ".join(available_stores)

        notification = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=(
                f"{part_number} is AVAILABLE!\n"
                f"{region}: {store_list}\n"
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


# Oregon / Pacific Timeで更新時刻を保存
checked_time = datetime.now(
    timezone.utc
).astimezone(
    ZoneInfo("America/Los_Angeles")
)

stock_data = {
    "updated": checked_time.strftime("%Y-%m-%d %H:%M:%S PT"),
    "products": all_products
}

with open("stock.json", "w", encoding="utf-8") as file:
    json.dump(
        stock_data,
        file,
        indent=2,
        ensure_ascii=False
    )

print("=" * 50)
print("stock.json updated.")
