import json
import logging
from typing import Optional, Dict, Any, List

from bot.config import config
from bot.utils.xui import api_request, get_inbound_data

logger = logging.getLogger(__name__)


def _parse_reality(inbound_data: Dict[str, Any]) -> tuple[str, str]:
    """Достаём short_id и spiderX из streamSettings инбаунда (та же логика, что в xui.py)."""
    default_short_id = getattr(config, 'SHORT_ID', '')
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
    return actual_sid, actual_spx


async def get_clients_by_tg_id(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает список всех клиентов (ключей/устройств) пользователя в инбаунде."""
    inbound_data = await get_inbound_data()
    if not inbound_data:
        return []

    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", [])

    user_clients = []
    for c in clients:
        # Проверяем по tgId (число или строка) или по префиксу в email (tg_1574885030_...)
        client_tg_id = c.get("tgId")
        email = c.get("email", "")
        
        is_matched_tg = client_tg_id is not None and str(client_tg_id) == str(user_id)
        is_matched_email = email.startswith(f"tg_{user_id}_") or email == f"tg_{user_id}"
        
        if is_matched_tg or is_matched_email:
            user_clients.append(c)

    return user_clients


async def get_vless_link_by_uuid(client_uuid: str) -> Optional[str]:
    """Находит клиента по UUID и собирает для него VLESS-ссылку."""
    inbound_data = await get_inbound_data()
    if not inbound_data:
        return None

    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", [])

    client = next((c for c in clients if c.get("id") == client_uuid), None)
    if not client:
        return None

    actual_sid, actual_spx = _parse_reality(inbound_data)

    public_key = getattr(config, 'PUBLIC_KEY', '')
    sni_domain = getattr(config, 'SNI_DOMAIN', 'www.cloudflare.com')
    panel_url = getattr(config, 'PANEL_URL', 'http://89.125.188.43:2053')
    server_ip = panel_url.rstrip('/').split("//")[1].split(":")[0]

    email = client.get("email", "device")
    tag = email.split("_")[-1] if "_" in email else email

    return (
        f"vless://{client_uuid}@{server_ip}:8443?encryption=none&flow=xtls-rprx-vision"
        f"&fp=firefox&pbk={public_key}&security=reality&sid={actual_sid}&sni={sni_domain}"
        f"&spx={actual_spx}&type=tcp#JempoVPN-{tag}"
    )


async def delete_client_by_uuid(client_uuid: str) -> bool:
    """Удаляет клиента (ключ/устройство) из инбаунда по UUID."""
    inbound_id = getattr(config, 'INBOUND_ID', 3)

    inbound_data = await get_inbound_data()
    if not inbound_data:
        return False

    settings_raw = inbound_data.get("settings", "{}")
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
    clients = settings.get("clients", [])

    new_clients = [c for c in clients if c.get("id") != client_uuid]
    if len(new_clients) == len(clients):
        # клиента с таким UUID не было — считаем, что удалять нечего
        return False

    settings["clients"] = new_clients
    inbound_data["settings"] = json.dumps(settings)

    if "streamSettings" in inbound_data and isinstance(inbound_data["streamSettings"], dict):
        inbound_data["streamSettings"] = json.dumps(inbound_data["streamSettings"])
    if "sniffing" in inbound_data and isinstance(inbound_data["sniffing"], dict):
        inbound_data["sniffing"] = json.dumps(inbound_data["sniffing"])

    update_res = await api_request("POST", f"/panel/api/inbounds/update/{inbound_id}", inbound_data)
    if not update_res or not update_res.get("success"):
        logger.error(f"Не удалось удалить клиента {client_uuid}: {update_res}")
        return False

    return True
