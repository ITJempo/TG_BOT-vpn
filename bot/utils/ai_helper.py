from google import genai
from bot.config import config

# Инициализируем клиент Google GenAI с вашим ключом
client = genai.Client(api_key=config.GEMINI_API_KEY)

async def ask_ai_support(user_message: str) -> str:
    try:
        # Используем быструю и бесплатную модель от Google (например, gemini-2.5-flash)
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=(
                "Ты — дружелюбный и компетентный специалист технической поддержки VPN-сервиса. "
                "Помогай пользователям настраивать подключение. "
                "Поддерживаемые приложения: "
                "1. Android: v2rayNG, Hiddify, Happ. "
                "2. iOS: V2Box, FoXray, Streisand, Happ. "
                "3. Windows: v2rayN, Hiddify. "
                "Объясняй простым языком, куда скопировать VLESS-ключ или ссылку на подписку. "
                "Отвечай коротко и вежливо.\n\n"
                f"Вопрос пользователя: {user_message}"
            ),
        )
        return response.text
    except Exception as e:
        return "⚠️ Произошла ошибка обращения к ИИ-помощнику. Попробуйте задать вопрос позже."