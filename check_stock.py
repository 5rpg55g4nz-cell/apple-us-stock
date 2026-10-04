import os
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import requests


APPLE_URL = "https://www.apple.com/shop/retail/pickup-message"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")

CONFIG_FILE = "products.json"
STOCK_FILE = "stock.json"
HISTORY_FILE = "history.json"

MAX_HISTORY_DAYS = 90


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )


def stock_key(part_number, region, store):
    return f"{part_number}|{region}|{store}"


def notification_matches(
    notification_config,
    part_number,
    region,
    store
):
    part_numbers = notification_config.get(
        "partNumbers",
        "all"
    )

    regions = notification_config.get(
        "regions",
        "all"
    )

    stores = notification_config.get(
        "stores",
        "all"
    )

    if (
        part_numbers != "all"
        and part_number not in part_numbers
    ):
        return False

    if (
        regions != "all"
        and region not in regions
    ):
        return False

    if (
        stores != "all"
        and store not in stores
    ):
        return False

    return True


config = load_json(CONFIG_FILE, {})

products = config.get("products", {})
regions = config.get("regions", [])

notification_config = config.get(
    "notifications",
    {
        "partNumbers": "all",
        "regions": "all",
        "stores": "all"
    }
)


old_data = load_json(
    STOCK_FILE,
    {"products": []}
)

history_data = load_json(
    HISTORY_FILE,
    {"events": []}
)

history_events = history_data.get(
    "events",
    []
)


previous_stock = {}

for product in old_data.get("products", []):

    part_number = product.get("partNumber")

    for region in product.get("regions", []):

        region_name = region.get("name")

        for store in region.get("stores", []):

            store_name = store.get("name")

            key = stock_key(
                part_number,
                region_name,
                store_name
            )

            previous_stock[key] = store.get(
                "available",
                False
            )


results = {}

for part_number, product_name in products.items():

    results[part_number] = {
        "partNumber": part_number,
        "name": product_name,
        "regions": []
    }


newly_available = []

now_utc = datetime.now(timezone.utc)


for region in regions:

    region_name = region["name"]
    zip_code = region["zipCode"]
    target_stores = region["stores"]

    print("=" * 60)
    print(f"Checking region: {region_name}")
    print(f"ZIP: {zip_code}")

    params = {
        "pl": "true",
        "location": zip_code
    }

    for index, part_number in enumerate(
        products.keys()
    ):
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
        timeout=30
    )

    print(
        f"HTTP Status: {response.status_code}"
    )

    response.raise_for_status()

    data = response.json()

    apple_stores = (
        data.get("body", {})
        .get("stores", [])
    )

    print(
        f"Apple returned "
        f"{len(apple_stores)} stores."
    )


    apple_store_map = {
        store.get("storeName", ""): store
        for store in apple_stores
    }


    for part_number, product_name in products.items():

        store_results = []

        for store_name in target_stores:

            apple_store = apple_store_map.get(
                store_name
            )

            if not apple_store:
                print(
                    f"Store missing from response: "
                    f"{store_name}"
                )
                continue


            availability = (
                apple_store
                .get("partsAvailability", {})
                .get(part_number, {})
            )

            pickup = availability.get(
                "pickupDisplay",
                "unknown"
            )

            is_available = (
                pickup == "available"
            )


            store_results.append({
                "name": store_name,
                "available": is_available
            })


            key = stock_key(
                part_number,
                region_name,
                store_name
            )


            had_previous_state = (
                key in previous_stock
            )

            was_available = previous_stock.get(
                key,
                False
            )


            if (
                had_previous_state
                and is_available != was_available
            ):

                event_type = (
                    "available"
                    if is_available
                    else "unavailable"
                )

                history_events.append({
                    "timestamp": (
                        now_utc
                        .isoformat()
                    ),
                    "partNumber": part_number,
                    "productName": product_name,
                    "region": region_name,
                    "store": store_name,
                    "status": event_type
                })

                print(
                    f"STATUS CHANGE: "
                    f"{product_name} / "
                    f"{store_name} / "
                    f"{event_type}"
                )


            if (
                is_available
                and not was_available
            ):

                newly_available.append({
                    "partNumber": part_number,
                    "productName": product_name,
                    "region": region_name,
                    "store": store_name
                })


        results[part_number]["regions"].append({
            "name": region_name,
            "stores": store_results
        })


cutoff = now_utc - timedelta(
    days=MAX_HISTORY_DAYS
)

clean_history = []

for event in history_events:

    try:
        event_time = datetime.fromisoformat(
            event["timestamp"]
        )

        if event_time >= cutoff:
            clean_history.append(event)

    except (
        KeyError,
        ValueError,
        TypeError
    ):
        pass


history_data = {
    "updated": now_utc.isoformat(),
    "events": clean_history
}

save_json(
    HISTORY_FILE,
    history_data
)


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

        should_notify = notification_matches(
            notification_config,
            item["partNumber"],
            item["region"],
            item["store"]
        )

        if not should_notify:

            print(
                "Notification filtered: "
                f"{item['productName']} / "
                f"{item['store']}"
            )

            continue


        if item["region"] == "Hawaii":

            local_zone = ZoneInfo(
                "Pacific/Honolulu"
            )

            zone_label = "HT"

        else:

            local_zone = ZoneInfo(
                "America/Los_Angeles"
            )

            zone_label = "PT"


        local_time = now_utc.astimezone(
            local_zone
        )


        time_text = local_time.strftime(
            "%b %d · %-I:%M %p"
        )


        message = (
            f"{item['productName']}\n"
            f"{item['store']} · "
            f"{item['region']}\n\n"
            f"Available at "
            f"{time_text} {zone_label}\n"
            f"{item['partNumber']}"
        )


        notification = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": "Stock Buddy",
                "Priority": "high"
            },
            timeout=20
        )

        notification.raise_for_status()

        print(
            "Notification sent: "
            f"{item['productName']} / "
            f"{item['store']}"
        )


else:

    print("=" * 60)
    print(
        "No newly available stock. "
        "No notification sent."
    )


checked_time = now_utc.astimezone(
    ZoneInfo("America/Los_Angeles")
)


stock_data = {
    "updated": checked_time.strftime(
        "%Y-%m-%d %H:%M:%S PT"
    ),
    "products": list(
        results.values()
    )
}


save_json(
    STOCK_FILE,
    stock_data
)


print("=" * 60)
print("stock.json updated.")
print(
    f"history.json updated. "
    f"{len(clean_history)} events stored."
)
