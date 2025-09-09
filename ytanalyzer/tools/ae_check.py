# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from ..config import Config


def main(argv: Optional[list[str]] = None) -> None:
    import argparse
    p = argparse.ArgumentParser(description="AliExpress API connectivity check")
    p.add_argument("--q", default="iphone case", help="Search query")
    p.add_argument("--n", type=int, default=3, help="Results to show")
    args = p.parse_args(argv)

    cfg = Config()
    if not (cfg.aliexpress_app_key and cfg.aliexpress_app_secret and cfg.aliexpress_tracking_id):
        print("AliExpress keys are missing. Set ALIEXPRESS_APP_KEY/SECRET/TRACKING_ID in .env")
        return

    try:
        from aliexpress_api import AliexpressApi  # type: ignore
    except Exception as e:
        print(f"aliexpress_api not installed or failed to import: {e}")
        print("Run: pip install python-aliexpress-api")
        return

    api = AliexpressApi(
        app_key=cfg.aliexpress_app_key,
        app_secret=cfg.aliexpress_app_secret,
        tracking_id=cfg.aliexpress_tracking_id,
    )

    try:
        res = api.search_products(keywords=args.q, page_no=1, page_size=max(1, min(10, args.n)))
        prods = (res or {}).get("products", [])[: args.n]
        if not prods:
            print("No products returned. Check API permissions/binding and keys.")
            return
        for i, p in enumerate(prods, 1):
            print(f"[{i}] id={p.get('productId')} price={p.get('targetSalePrice')} title={p.get('productTitle')}\n    {p.get('productUrl')}")
    except Exception as e:
        print(f"API error: {e}")


if __name__ == "__main__":
    main()

