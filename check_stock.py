import os
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests


APPLE_URL = "https://www.apple.com/shop/retail/pickup-message"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")


# ========================================
# products.json を読み込む
# ========================================

with open("products.json", "r", encoding="utf-8") as file:
    config = json.load(file)

products = config["products"]
regions = config["regions"]


# ========================================
# 前回の在庫状況を読み込む
# ========================================

previous_stock = {}

try:
    with open("stock.json", "r", encoding="utf-8") as file:
        old_data = json.load(file)

    # 新しい形式の stock.json
    for product in old_data.get("products", []):
        part_number = product.get("partNumber")

        for region in product.get("regions", []):
            region_name = region.get("name")

            for store in region.get("stores", []):
                store_name = store.get("name")

                key = (
                    f"{part_number}|"
                    f"{region_name}|"
                    f"{store_name}"
                )

                previous_stock[key] = store.get(
                    "available",
                    False
                )

except (FileNotFoundError, json.JSONDecodeError):
    print("Previous stock data not found.")


# ========================================
# 結果を入れる箱を作る
# ========================================

results = {}

for part_number, product_name in products.items():

    results[part_number] = {
        "partNumber": part_number,
        "name": product_name,
        "regions": []
    }


newly_available = []


# ========================================
# 地域ごとにAppleへ問い合わせ
# ========================================

for region in regions:

    region_name = region["name"]
    zip_code = region["zipCode"]
    target_stores = set(region["stores"])

    print("=" * 60)
    print(f"Checking region: {region_name}")
    print(f"ZIP: {zip_code}")

    # 32 SKUを1つのリクエストにまとめる
    params = {
        "pl": "true",
        "location": zip_code
    }

    for index, part_number in enumerate(products.keys()):
        params[f"parts.{index}"] = part_number

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "Version/18.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.apple.com/shop/",
    }

    response = requests.get(
        APPLE_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    print(f"HTTP Status: {response.status_code}")

    response.raise_for_status()

    data = response.json()

    apple_stores = (
        data.get("body", {})
        .get("stores", [])
    )

    print(
        f"Apple returned {len(apple_stores)} stores."
    )


    # ====================================
    # 各SKUについて店舗在庫を確認
    # ====================================

    for part_number, product_name in products.items():

        store_results = []

        for store in apple_stores:

            store_name = store.get("storeName", "")

            if store_name not in target_stores:
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

            store_results.append({
                "name": store_name,
                "available": is_available
            })

            key = (
                f"{part_number}|"
                f"{region_name}|"
                f"{store_name}"
            )

            was_available = previous_stock.get(
                key,
                False
            )

            # 前回 🔴 → 今回 🟢 の時だけ通知対象
            if is_available and not was_available:

                newly_available.append({
                    "partNumber": part_number,
                    "productName": product_name,
                    "region": region_name,
                    "store": store_name
                })

                print(
                    f"🚨 NEW STOCK: "
                    f"{product_name} / "
                    f"{store_name}"
                )

        results[part_number]["regions"].append({
            "name": region_name,
            "stores": store_results
        })


# ========================================
# 新規在庫を通知
# ========================================

if newly_available:

    if not NTFY_TOPIC:
        raise RuntimeError(
            "NTFY_TOPIC is not configured"
        )

    print("=" * 60)
    print(
        f"New stock found: "
        f"{len(newly_available)}"
    )

    for item in newly_available:

        message = (
            f"{item['productName']}\n"
            f"{item['partNumber']}\n"
            f"Store: {item['store']}\n"
            f"Region: {item['region']}\n"
            f"Check Apple Store now."
        )

        notification = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Apple US Stock Found!",
                "Priority": "urgent",
                "Tags": "apple,rotating_light",
            },
            timeout=20,
        )

        notification.raise_for_status()

else:

    print("=" * 60)
    print(
        "No newly available stock. "
        "No notification sent."
    )


# ========================================
# stock.json を作成
# ========================================

checked_time = datetime.now(
    timezone.utc
).astimezone(
    ZoneInfo("America/Los_Angeles")
)

stock_data = {
    "updated": checked_time.strftime(
        "%Y-%m-%d %H:%M:%S PT"
    ),
    "products": list(results.values())
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


print("=" * 60)
print("stock.json updated.")
