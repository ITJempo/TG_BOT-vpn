from bot.utils.xui import generate_vpn_key as xui_generate_vpn_key

class VPNPanelService:
    @staticmethod
    async def generate_vpn_key(user_id: int, username: str, days: int = 30) -> str:
        return await xui_generate_vpn_key(user_id, username, days)