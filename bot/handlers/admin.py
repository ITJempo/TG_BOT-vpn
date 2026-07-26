import asyncio
import json
import time
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery, FSInputFile, InputMediaPhoto

from bot.config import config, BASE_DEVICES
from bot.database.db import db
from bot.keyboards.callbacks import AdminNavCallback, NavCallback
from bot.utils.xui import (
    get_unique_users_count, 
    get_inbound_data, 
    find_client_by_tg_id, 
    generate_vpn_key,
    add_extra_device,
)

router = Router()

# Гарантируем, что ADMIN_ID — это int
ADMIN_ID = int(config.ADMIN_ID)

# Путь к баннеру (используется общий стиль с остальным ботом)
BANNER_START = "bot/assets/start_banner.png"


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_lookup = State()


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Всего юзеров", callback_data="adm_users_count"),
            InlineKeyboardButton(text="🔍 Найти юзера", callback_data="adm_lookup")
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"),
            InlineKeyboardButton(text="📈 Состояние узла", callback_data="adm_status")
        ],
        [
            InlineKeyboardButton(text="🎁 Выдать подписку (/give)", callback_data="adm_give_help")
        ],
        [
            InlineKeyboardButton(text="◀️ В главное меню", callback_data=NavCallback(target="home").pack())
        ]
    ])


# --- Безопасное обновление сообщений с баннером для админки ---
async def safe_edit_admin_message(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    try:
        if callback.message.photo:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(BANNER_START),
                    caption=text,
                    parse_mode="Markdown"
                ),
                reply_markup=reply_markup
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile(BANNER_START),
                caption=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception:
        try:
            await callback.message.answer_photo(
                photo=FSInputFile(BANNER_START),
                caption=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


# --- ГЛАВНОЕ ОКНО АДМИНКИ ---
@router.callback_query(AdminNavCallback.filter(F.action == "main"))
@router.callback_query(F.data == "admin_panel")
async def admin_panel_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    text = (
        "👑 **АДМИНИСТРАТИВНАЯ ПАНЕЛЬ**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Добро пожаловать в панель управления ботом!\n"
        "Выберите нужное действие ниже:"
    )
    await safe_edit_admin_message(callback, text, get_admin_menu())
    await callback.answer()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    text = (
        "👑 **АДМИНИСТРАТИВНАЯ ПАНЕЛЬ**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Выберите нужный инструмент:"
    )
    try:
        await message.answer_photo(
            photo=FSInputFile(BANNER_START),
            caption=text,
            reply_markup=get_admin_menu(),
            parse_mode="Markdown"
        )
    except Exception:
        await message.answer(text, reply_markup=get_admin_menu(), parse_mode="Markdown")


# --- 1. СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ ---
@router.callback_query(F.data == "adm_users_count")
async def adm_users_count_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    unique_count = await get_unique_users_count()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ В админку", callback_data=AdminNavCallback(action="main").pack())
    ]])
    
    text = (
        f"📊 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ**\n\n"
        f"👥 Всего уникальных клиентов в базе: `{unique_count}`"
    )
    await safe_edit_admin_message(callback, text, keyboard)
    await callback.answer()


# --- 2. ПОИСК ПОЛЬЗОВАТЕЛЯ ---
@router.callback_query(F.data == "adm_lookup")
async def adm_lookup_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_user_lookup)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data=AdminNavCallback(action="main").pack())
    ]])
    text = "👤 **Введите Telegram ID пользователя для поиска:**"
    await safe_edit_admin_message(callback, text, keyboard)
    await callback.answer()


@router.message(AdminStates.waiting_for_user_lookup)
async def adm_lookup_execute(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный формат ID. Напишите только число.")
        return

    client = await find_client_by_tg_id(target_id)
    if not client:
        await message.answer(f"❌ Пользователь `{target_id}` не найден в базе.", parse_mode="Markdown")
        return

    expiry_ms = client.get("expiryTime", 0)
    email = client.get("email")
    is_enabled = client.get("enable")
    
    text = (
        f"👤 **ИНФОРМАЦИЯ О КЛИЕНТЕ:**\n\n"
        f"🆔 **ID:** `{target_id}`\n"
        f"📧 **Email:** `{email}`\n"
        f"🟢 **Активен:** `{is_enabled}`\n"
        f"⏳ **Expiry (ms):** `{expiry_ms}`"
    )
    
    try:
        await message.answer_photo(
            photo=FSInputFile(BANNER_START),
            caption=text,
            reply_markup=get_admin_menu(),
            parse_mode="Markdown"
        )
    except Exception:
        await message.answer(text, reply_markup=get_admin_menu(), parse_mode="Markdown")


# --- 3. РАССЫЛКА СООБЩЕНИЙ ---
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_broadcast)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data=AdminNavCallback(action="main").pack())
    ]])
    text = "📢 **Отправьте сообщение для рассылки всем пользователям:**"
    await safe_edit_admin_message(callback, text, keyboard)
    await callback.answer()


@router.message(AdminStates.waiting_for_broadcast)
async def adm_broadcast_execute(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.clear()
    
    inbound_data = await get_inbound_data()
    if not inbound_data:
        await message.answer("❌ Ошибка связи с панелью 3X-UI.")
        return

    clients = json.loads(inbound_data.get("settings", "{}")).get("clients", [])
    sent_count = 0
    
    status_msg = await message.answer("🚀 Рассылка запущена...")
    for client in clients:
        tg_id = client.get("tgId")
        if tg_id:
            try:
                await message.send_copy(chat_id=tg_id)
                sent_count += 1
                await asyncio.sleep(0.04)
            except Exception:
                pass
                
    text = f"✅ **Рассылка завершена!**\nДоставлено сообщений: `{sent_count}`"
    try:
        await status_msg.delete()
        await message.answer_photo(
            photo=FSInputFile(BANNER_START),
            caption=text,
            reply_markup=get_admin_menu(),
            parse_mode="Markdown"
        )
    except Exception:
        await status_msg.edit_text(text, parse_mode="Markdown", reply_markup=get_admin_menu())


# --- 4. СОСТОЯНИЕ УЗЛА СЕРВЕРА ---
@router.callback_query(F.data == "adm_status")
async def adm_status_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    unique_users = await get_unique_users_count()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ В админку", callback_data=AdminNavCallback(action="main").pack())
    ]])
    
    text = (
        f"📈 **СВОДКА СИСТЕМЫ**\n\n"
        f"🔗 Инбаунд ID: `{config.INBOUND_ID}`\n"
        f"👥 Активных пользователей: `{unique_users}`\n"
        f"🟢 Статус: Онлайн"
    )
    await safe_edit_admin_message(callback, text, keyboard)
    await callback.answer()


# --- 5. СПРАВКА ПО ВЫДАЧЕ КЛЮЧЕЙ ---
@router.callback_query(F.data == "adm_give_help")
async def adm_give_help_handler(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ В админку", callback_data=AdminNavCallback(action="main").pack())
    ]])
    
    text = (
        "🎁 **ВЫДАЧА / ПРОДЛЕНИЕ ПОДПИСКИ**\n\n"
        "Чтобы выдать или продлить подписку пользователю вручную, отправьте команду в чат:\n\n"
        "👉 `/give <ID_пользователя> <дней> [устройств]`\n\n"
        "**Примеры:**\n"
        "`/give 1574885030 30` — 30 дней, устройств по умолчанию.\n"
        f"`/give 1574885030 30 5` — 30 дней и 5 устройств (создаст основной ключ + доп. ключи)."
    )
    await safe_edit_admin_message(callback, text, keyboard)
    await callback.answer()


# --- 6. КОМАНДА /give ---
@router.message(Command("give"))
async def cmd_give(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Использование: `/give <user_id> [дни] [устройств]`", parse_mode="Markdown")
        return

    try:
        target_user_id = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 30
        device_count = int(parts[3]) if len(parts) > 3 else BASE_DEVICES
    except ValueError:
        await message.answer("❌ Указывайте ID, дни и количество устройств числами.")
        return

    if device_count < 1:
        await message.answer("❌ Количество устройств должно быть не меньше 1.")
        return

    # 1. Генерируем/продлеваем ОСНОВНОЙ ключ в 3X-UI
    vpn_config = await generate_vpn_key(target_user_id, "AdminUser", days=days)

    if vpn_config and str(vpn_config).startswith("vless://"):
        # 1.1 Создаём дополнительные ключи (устройства) сверх основного
        extra_keys = []
        for _ in range(max(0, device_count - 1)):
            extra_key = await add_extra_device(target_user_id, days=days)
            if extra_key and str(extra_key).startswith("vless://"):
                extra_keys.append(extra_key)

        # 2. Обновляем подписку в локальной базе данных (SQLite)
        user = await db.get_user(target_user_id)
        now_ms = int(time.time() * 1000)
        current_expiry = user.get("expiry_time", 0) if user else 0
        base_time = max(current_expiry, now_ms) if current_expiry > now_ms else now_ms
        new_expiry = base_time + (days * 24 * 60 * 60 * 1000)

        await db.add_or_update_user(
            user_id=target_user_id,
            username=user.get("username", "User") if user else "User",
            email=f"tg_{target_user_id}",
            expiry_time=new_expiry
        )

        await db.set_device_limit(target_user_id, device_count)

        # 3. Отправляем подтверждение админу
        extra_block = ""
        for idx, ek in enumerate(extra_keys, start=2):
            extra_block += f"\n🔑 **Ключ #{idx}:**\n`{ek}`\n"

        await message.answer(
            f"✅ **Ключ(и) успешно созданы и сохранены в базе!**\n\n"
            f"👤 **Пользователь:** `{target_user_id}`\n"
            f"📅 **Дней:** `{days}`\n"
            f"📱 **Устройств:** `{1 + len(extra_keys)}`\n\n"
            f"🔑 **Ключ #1:**\n`{vpn_config}`\n"
            f"{extra_block}",
            parse_mode="Markdown"
        )
        
        # 4. Отправляем уведомление пользователю
        try:
            user_msg = (
                f"🎉 **Ваша подписка продлена администратором на {days} дней!**\n\n"
                f"📱 Устройств: {1 + len(extra_keys)}\n\n"
                f"🔑 **Ключ #1:**\n`{vpn_config}`\n"
                f"{extra_block}"
            )
            await message.bot.send_message(target_user_id, user_msg, parse_mode="Markdown")
        except Exception:
            pass
    else:
        await message.answer(f"❌ Ошибка генерации ключа: {vpn_config}")