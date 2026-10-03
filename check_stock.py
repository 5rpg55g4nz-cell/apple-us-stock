import os
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

APPLE_URL = "https://www.apple.com/shop/retail/pickup-message"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


# ========================================
# 前回の在庫状況を読み込む
# ========================================

previous_stock = {}

try:
    with open("stock.json", "r", encoding="utf-8") as file:
        old_data = json.load(file)

    for product in old_data.get("products", []):
        part_number = product.get("partNumber")

        for store in product.get("stores", []):
            key = f"{part_number}|{store.get('name')}"
            previous_stock[key] = store.get("available", False)

except (FileNotFoundError, json.JSONDecodeError):
    print("Previous stock data not found.")


# ========================================
# 監視設定を読み込む
# ========================================

with open("products.json", "r", encoding="utf-8") as file:
    config = json.load(file)


all_products = []
newly_available = []


# ========================================
# Appleの在庫をチェック
# ========================================

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

    for store in apple_stores:

        name = store.get("storeName", "")

        if name not in target_stores:
            continue

        availability = (
            store.get("partsAvailability", {})
            .get(part_number, {})
        )

        pickup = availability.get(
            "pickupDisplay",
            "unknown"
        )

        is_available = pickup == "available"

        results.append({
            "name": name,
            "available": is_available
        })

        key = f"{part_number}|{name}"

        was_available = previous_stock.get(
            key,
            False
        )

        # 前回は在庫なし、今回は在庫あり
        if is_available and not was_available:

            newly_available.append({
                "partNumber": part_number,
                "region": region,
                "store": name
            })

            print(
                f"🚨 NEW STOCK: "
                f"{part_number} / {name}"
            )

        symbol = "🟢" if is_available else "🔴"
        status = (
            "AVAILABLE"
            if is_available
            else "UNAVAILABLE"
        )

        print(
            f"{symbol} {name}: {status}"
        )

    all_products.append({
        "partNumber": part_number,
        "name": product.get(
            "name",
            part_number
        ),
        "region": region,
        "stores": results
    })


# ========================================
# 新しく在庫が出た場合だけ通知
# ========================================

if newly_available:

    if not NTFY_TOPIC:
        raise RuntimeError(
            "NTFY_TOPIC is not configured"
        )

    for item in newly_available:

        message = (
            f"{item['partNumber']} is AVAILABLE!\n"
            f"Store: {item['store']}\n"
            f"Region: {item['region']}\n"
            f"Check Apple Store now."
        )

        notification = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":
                    "Apple US Stock Found!",
                "Priority": "urgent",
                "Tags":
                    "apple,rotating_light",
            },
            timeout=20,
        )

        notification.raise_for_status()

else:
    print(
        "No newly available stock. "
        "No notification sent."
    )


# ========================================
# 新しい在庫状況を保存
# ========================================

checked_time = datetime.now(
    timezone.utc
).astimezone(
    ZoneInfo("America/Los_Angeles")
)

stock_data = {
    "updated":
        checked_time.strftime(
            "%Y-%m-%d %H:%M:%S PT"
        ),
    "products": all_products
}

with open(
    "stock.json",
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        stock_data,
        file,
        indent=2,
        ensure_ascii=False
    )

print("=" * 50)
print("stock.json updated.")
