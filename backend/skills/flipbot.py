"""
FlipBot — Screenshot-to-Listing Arbitrage Agent
Vision extraction + eBay sold comps + optimized resale listing + profit calc.
Works with base64 images (web) or raw bytes (Telegram).
"""

import os
import json
import base64
import logging
import requests
from typing import Optional

log = logging.getLogger("FlipBot")

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EBAY_APP_ID = os.environ.get("EBAY_APP_ID", "")

FEES = {
    "ebay":     0.13,
    "facebook": 0.05,
    "offerup":  0.129,
    "mercari":  0.10,
    "local":    0.0,
}


def get_ebay_sold_comps(query: str) -> dict:
    """Pull recently sold eBay listings for price comps."""
    if not EBAY_APP_ID:
        return {"avg": None, "low": None, "high": None, "count": 0, "error": "No EBAY_APP_ID set"}
    url = "https://svcs.ebay.com/services/search/FindingService/v1"
    params = {
        "OPERATION-NAME": "findCompletedItems",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": EBAY_APP_ID,
        "RESPONSE-DATA-FORMAT": "JSON",
        "keywords": query,
        "itemFilter(0).name": "SoldItemsOnly",
        "itemFilter(0).value": "true",
        "sortOrder": "EndTimeSoonest",
        "paginationInput.entriesPerPage": "10",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        items = (
            data.get("findCompletedItemsResponse", [{}])[0]
            .get("searchResult", [{}])[0]
            .get("item", [])
        )
        prices = [
            float(i["sellingStatus"][0]["currentPrice"][0]["__value__"])
            for i in items
        ]
        if not prices:
            return {"avg": None, "low": None, "high": None, "count": 0}
        return {
            "avg": round(sum(prices) / len(prices), 2),
            "low": round(min(prices), 2),
            "high": round(max(prices), 2),
            "count": len(prices),
        }
    except Exception as e:
        log.error(f"eBay API error: {e}")
        return {"avg": None, "low": None, "high": None, "count": 0, "error": str(e)}


def extract_listing_from_image(image_b64: str) -> dict:
    """Use Claude vision to extract item details from a screenshot."""
    if not ANTHROPIC_KEY:
        return {"error": "No ANTHROPIC_API_KEY set"}
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract info from this product listing screenshot. "
                            "Return ONLY valid JSON with these fields: "
                            '{"item_name": "", "asking_price": 0.0, "condition": "", '
                            '"platform": "", "key_specs": [], "seller_notes": ""}. '
                            "No markdown, no explanation, just JSON."
                        )
                    }
                ]
            }]
        )
        raw = resp.content[0].text.strip()
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)}


def generate_listing(item: dict, comps: dict, platform: str = "ebay") -> dict:
    """Generate an optimized resale listing with profit calculation."""
    if not ANTHROPIC_KEY:
        return {"error": "No ANTHROPIC_API_KEY set"}

    fee = FEES.get(platform, 0.13)
    suggested_list = est_net = est_profit = profit_pct = None

    if comps.get("avg"):
        suggested_list = round(comps["avg"] * 0.92, 2)
        est_net = round(suggested_list * (1 - fee), 2)
        buy_price = item.get("asking_price", 0) or 0
        est_profit = round(est_net - buy_price, 2)
        profit_pct = round((est_profit / buy_price * 100) if buy_price else 0, 1)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        prompt = f"""
You are a professional resale listing writer.

Item details:
{json.dumps(item, indent=2)}

eBay sold comps:
{json.dumps(comps, indent=2)}

Write a complete resale listing. Return ONLY valid JSON:
{{
  "title": "(max 80 chars, keyword-rich, no caps spam)",
  "description": "(3-5 sentences: condition, specs, why it's a great deal)",
  "price_recommendation": {suggested_list or 'null'},
  "platform_notes": "(platform-specific tips)"
}}
No markdown, just JSON.
"""
        resp = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        listing = json.loads(resp.content[0].text.strip())
        listing["comps"] = comps
        listing["est_profit"] = est_profit
        listing["profit_pct"] = profit_pct
        listing["net_after_fees"] = est_net
        listing["fee_pct"] = int(fee * 100)
        listing["platform"] = platform
        return listing
    except Exception as e:
        return {"error": str(e)}


async def analyze_listing(image_b64: str, platform: str = "ebay") -> dict:
    """
    Full pipeline: image → extract → comps → listing.
    Returns complete analysis dict.
    """
    # 1. Extract item from image
    item = extract_listing_from_image(image_b64)
    if "error" in item:
        return {"stage": "extraction", "error": item["error"]}

    # 2. Pull comps
    comps = get_ebay_sold_comps(item.get("item_name", ""))

    # 3. Generate listing
    listing = generate_listing(item, comps, platform)
    if "error" in listing:
        return {"stage": "listing", "error": listing["error"], "item": item, "comps": comps}

    # 4. Build profit badge
    profit_emoji = ""
    if listing.get("profit_pct") is not None:
        pct = listing["profit_pct"]
        profit_emoji = "🔥" if pct > 40 else "💰" if pct > 20 else "⚠️"

    return {
        "success": True,
        "item": item,
        "comps": comps,
        "listing": listing,
        "profit_emoji": profit_emoji,
        "summary": {
            "item_name": item.get("item_name", "Unknown"),
            "asking_price": item.get("asking_price"),
            "list_at": listing.get("price_recommendation"),
            "est_profit": listing.get("est_profit"),
            "profit_pct": listing.get("profit_pct"),
            "ebay_avg": comps.get("avg"),
            "comp_count": comps.get("count", 0),
        }
    }


def scan_item(query: str) -> dict:
    """Quick comp scan without image — just item name."""
    comps = get_ebay_sold_comps(query)
    if not comps.get("avg"):
        return {"query": query, "comps": comps, "found": False}
    suggested = round(comps["avg"] * 0.92, 2)
    return {
        "query": query,
        "comps": comps,
        "found": True,
        "list_at": suggested,
        "undercut_pct": 8,
    }
