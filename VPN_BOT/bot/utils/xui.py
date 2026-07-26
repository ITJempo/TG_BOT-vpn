import json
import time
import uuid
import logging
import aiohttp
from typing import Optional, Dict, Any

from bot.config import config

logger = logging.getLogger(__name__)

async def add_extra_device(user_id: int, days: int = 30) -> str:
    """Генерирует НОВЫЙ ключ для дополнительного устройства пользователя."""
    inbound_id = getattr(config, 'INBOUND_ID', 3)
    public_key = getattr(config, 'PUBLIC_KEY', '')
    sni_domain = getattr(config, 'SNI_DOMAIN', 'www.cloudflare.com')
    default_short_id = getattr(config, 'SHORT_ID', '')
    panel_url = getattr(config, 'PANEL_URL', 'http://89.125.188.43:2053')

    inbound_data = await get_inbound_data()
    if not inbound_data:
        return "Ошибка связи с панелью 3X-UI."

    try:
        stream_settings = json.loads(inbound_data.get("streamSettings", "{}"))
        reality_settings = stream_settings.get("realitySettings", {})
        short_ids_list = reality_settings.get("shortIds", [])
        actual_sid = short_ids_list[0] if short_ids_list else default_short_id
        settings_dest = reality_settings.get("settings", {})
        actual_spx = settings_dest.get("spiderX", "/nb9qTXB1YtRbyd")
    except Exception:
        actual_sid = default_short_id
        actual_spx = "/nb9qTXB1YtRbyd"

    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    if "clients" not in settings:
        settings["clients"] = []

    # Создаем НОВОГО клиента с уникальным суффиксом
    client_uuid = str(uuid.uuid4())
    unique_suffix = uuid.uuid4().hex[:4]
    email_str = f"tg_{user_id}_dev_{unique_suffix}"
    client_sub_id = uuid.uuid4().hex[:16]
    password_str = uuid.uuid4().hex[:8]
    expiry_time_ms = int((time.time() + (days * 24 * 60 * 60)) * 1000)

    new_client = {
        "id": client_uuid,
        "email": email_str,
        "password": password_str,
        "alterId": 0,
        "limitIp": 0,          
        "totalGB": 0,          
        "expiryTime": expiry_time_ms,  
        "enable": True,
        "flow": "xtls-rprx-vision",
        "tgId": int(user_id),
        "subId": client_sub_id,
        "reset": 0
    }
    settings["clients"].append(new_client)

    inbound_data["settings"] = json.dumps(settings)
    if "streamSettings" in inbound_data and isinstance(inbound_data["streamSettings"], dict):
        inbound_data["streamSettings"] = json.dumps(inbound_data["streamSettings"])
    if "sniffing" in inbound_data and isinstance(inbound_data["sniffing"], dict):
        inbound_data["sniffing"] = json.dumps(inbound_data["sniffing"])

    update_res = await api_request("POST", f"/panel/api/inbounds/update/{inbound_id}", inbound_data)
    if not update_res or not update_res.get("success"):
        return f"Ошибка сохранения в панели: {update_res.get('msg') if update_res else 'Unknown'}"

    server_ip = panel_url.rstrip('/').split("//")[1].split(":")[0]
    return f"vless://{client_uuid}@{server_ip}:8443?encryption=none&flow=xtls-rprx-vision&fp=firefox&pbk={public_key}&security=reality&sid={actual_sid}&sni={sni_domain}&spx={actual_spx}&type=tcp#JempoVPN-Device-{unique_suffix}"

async def api_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        panel_url = getattr(config, 'PANEL_URL', 'http://89.125.188.43:2053').rstrip('/')
        api_token = getattr(config, 'API_TOKEN', '')
        
        url = f"{panel_url}{endpoint}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_token}"
        }
        try:
            if method == "GET":
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
            elif method == "POST":
                async with session.post(url, json=data, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"Panel API Exception [{method} {endpoint}]: {e}")
            
        return {"success": False, "msg": "Network or Parse Error"}


async def get_inbound_data() -> Optional[Dict[str, Any]]:
    inbound_id = getattr(config, 'INBOUND_ID', 3)
    res = await api_request("GET", f"/panel/api/inbounds/get/{inbound_id}")
    if res and res.get("success"):
        return res.get("obj", {})
    return None


async def get_unique_users_count() -> int:
    inbound_data = await get_inbound_data()
    if not inbound_data:
        return 0
    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", [])
    
    unique_ids = {c.get("tgId") for c in clients if c.get("tgId") and c.get("tgId") != 0}
    return len(unique_ids)


async def find_client_by_tg_id(user_id: int) -> Optional[Dict[str, Any]]:
    inbound_data = await get_inbound_data()
    if not inbound_data:
        return None
    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", [])
    return next((c for c in clients if c.get("tgId") == user_id), None)


async def generate_vpn_key(user_id: int, username: str, days: int = 30) -> str:
    inbound_id = getattr(config, 'INBOUND_ID', 3)
    public_key = getattr(config, 'PUBLIC_KEY', '')
    sni_domain = getattr(config, 'SNI_DOMAIN', 'www.cloudflare.com')
    default_short_id = getattr(config, 'SHORT_ID', '')
    panel_url = getattr(config, 'PANEL_URL', 'http://89.125.188.43:2053')

    inbound_data = await get_inbound_data()
    if not inbound_data:
        return "Ошибка связи с панелью 3X-UI."

    try:
        stream_settings = json.loads(inbound_data.get("streamSettings", "{}"))
        reality_settings = stream_settings.get("realitySettings", {})
        short_ids_list = reality_settings.get("shortIds", [])
        actual_sid = short_ids_list[0] if short_ids_list else default_short_id
        settings_dest = reality_settings.get("settings", {})
        actual_spx = settings_dest.get("spiderX", "/nb9qTXB1YtRbyd")
    except Exception:
        actual_sid = default_short_id
        actual_spx = "/nb9qTXB1YtRbyd"

    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    if "clients" not in settings:
        settings["clients"] = []

    existing_client = next((c for c in settings["clients"] if c.get("tgId") == user_id or str(c.get("email","")).startswith(f"tg_{user_id}")), None)
    
    if existing_client:
        client_uuid = existing_client["id"]
        current_expiry = existing_client.get("expiryTime", 0)
        now_ms = int(time.time() * 1000)
        
        base_time = max(current_expiry, now_ms) if current_expiry > now_ms else now_ms
        new_expiry_ms = base_time + (days * 24 * 60 * 60 * 1000)
        
        existing_client["expiryTime"] = new_expiry_ms
        existing_client["enable"] = True
    else:
        client_uuid = str(uuid.uuid4())
        unique_suffix = uuid.uuid4().hex[:6]
        email_str = f"tg_{user_id}_{unique_suffix}"
        client_sub_id = uuid.uuid4().hex[:16]
        password_str = uuid.uuid4().hex[:8]
        expiry_time_ms = int((time.time() + (days * 24 * 60 * 60)) * 1000)

        new_client = {
            "id": client_uuid,
            "email": email_str,
            "password": password_str,
            "alterId": 0,
            "limitIp": 0,          
            "totalGB": 0,          
            "expiryTime": expiry_time_ms,  
            "enable": True,
            "flow": "xtls-rprx-vision",
            "tgId": int(user_id),
            "subId": client_sub_id,
            "reset": 0
        }
        settings["clients"].append(new_client)

    # 3X-UI требует, чтобы settings, streamSettings и sniffing были переданы как JSON-строки
    inbound_data["settings"] = json.dumps(settings)
    if "streamSettings" in inbound_data and isinstance(inbound_data["streamSettings"], dict):
        inbound_data["streamSettings"] = json.dumps(inbound_data["streamSettings"])
    if "sniffing" in inbound_data and isinstance(inbound_data["sniffing"], dict):
        inbound_data["sniffing"] = json.dumps(inbound_data["sniffing"])

    # Отправляем на документированный эндпоинт обновления инбаунда
    update_res = await api_request("POST", f"/panel/api/inbounds/update/{inbound_id}", inbound_data)
    if not update_res or not update_res.get("success"):
        return f"Ошибка сохранения в панели: {update_res.get('msg') if update_res else 'Unknown'}"

    server_ip = panel_url.rstrip('/').split("//")[1].split(":")[0]
    return f"vless://{client_uuid}@{server_ip}:8443?encryption=none&flow=xtls-rprx-vision&fp=firefox&pbk={public_key}&security=reality&sid={actual_sid}&sni={sni_domain}&spx={actual_spx}&type=tcp#JempoVPN-{user_id}"