from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    db_path: str = os.getenv("DB_PATH", "data/yutura.sqlite")
    rss_db_path: str = os.getenv("RSS_DB_PATH", "data/rss_watch.sqlite")
    yutura_cookie: str | None = os.getenv("YUTURA_COOKIE") or None
    cookies_txt: str | None = os.getenv("COOKIES_TXT") or None
    cookies_json: str | None = os.getenv("COOKIES_JSON") or None
    deepseek_api_key: str | None = os.getenv("DEEPSEEK_API_KEY") or None
    # AliExpress (optional; used by resale MVP)
    aliexpress_app_key: str | None = os.getenv("ALIEXPRESS_APP_KEY") or None
    aliexpress_app_secret: str | None = os.getenv("ALIEXPRESS_APP_SECRET") or None
    aliexpress_tracking_id: str | None = os.getenv("ALIEXPRESS_TRACKING_ID") or None
    # Profit estimation params (tweak as needed)
    market_fee_rate: float = float(os.getenv("YAHOO_FEE_RATE", "0.10"))
    fx_usdjpy: float = float(os.getenv("FX_USDJPY", "155.0"))
    ae_shipping_jpy: float = float(os.getenv("AE_SHIPPING_JPY", "0"))
    yahoo_shipping_income_jpy: float = float(os.getenv("YAHOO_SHIPPING_INCOME_JPY", "0"))
    misc_cost_jpy: float = float(os.getenv("MISC_COST_JPY", "0"))
