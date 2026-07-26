import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
class Settings(BaseSettings):
    BOT_TOKEN: str
    PANEL_URL: str
    INBOUND_ID: int
    API_TOKEN: str
    PUBLIC_KEY: str
    SHORT_ID: str
    SNI_DOMAIN: str
    
    ADMIN_USERNAME: str
    ADMIN_ID: int
    
    DB_PATH: str = "bot_database.db"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

config = Settings()

# ──────────────────────────────────────────────────────────────
# ТАРИФНЫЕ ПЛАНЫ
# old_stars — "старая" цена, которая рисуется зачёркнутой на кнопке (маркетинг).
# stars     — реальная цена в Telegram Stars (это единственный подключённый способ оплаты).
# ──────────────────────────────────────────────────────────────
PRICING_PLANS = {
    "sub_7_days":   {"days": 7,   "old_stars": 45,   "stars": 25,  "title": "Неделя",     "desc": "Доступ к скоростному VPN на 7 дней."},
    "sub_30_days":  {"days": 30,  "old_stars": 150,  "stars": 75,  "title": "Месяц",      "desc": "Месяц быстрого и стабильного VPN без ограничений."},
    "sub_90_days":  {"days": 90,  "old_stars": 400,  "stars": 200, "title": "3 Месяца",   "desc": "3 месяца премиум соединения со скидкой."},
    "sub_180_days": {"days": 180, "old_stars": 650,  "stars": 450, "title": "6 Месяцев",  "desc": "Полгода VPN по выгодной цене."},
    "sub_365_days": {"days": 365, "old_stars": 1300, "stars": 650, "title": "1 Год",      "desc": "Максимальная экономия — целый год без забот."},
}

# Сколько устройств входит в тариф "из коробки" и сколько стоит каждое доп. устройство
BASE_DEVICES = 2
MAX_DEVICES = 13
EXTRA_DEVICE_STARS = 15

# Пробный период
TRIAL_DAYS = 3
TRIAL_DEVICES = 2

# Простейшие промокоды. Два вида:
#  - {"discount_stars": N}  — скидка N звёзд при следующей оплате
#  - {"free_days": N}       — сразу начисляет N дней подписки бесплатно, без оплаты
# Пока хранится в коде, для полноценной системы промокодов лучше вынести в БД.
PROMO_CODES = {
    "WELCOME10": {"discount_stars": 10},
    "JEMPO50": {"discount_stars": 50},
    "FREE7": {"free_days": 7},
}

# Загружаем переменные из .env файла
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PANEL_URL = os.getenv("PANEL_URL", "")
API_TOKEN = os.getenv("API_TOKEN", "")

# ⚠️ Убедись, что переменная называется именно ADMIN_ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "1574885030"))  # Твой Telegram ID
INBOUND_ID = int(os.getenv("INBOUND_ID", "3"))       # ID инбаунда в 3X-UI
