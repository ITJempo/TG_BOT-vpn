import time
import uuid
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InputMediaPhoto
from aiocryptopay import AioCryptoPay, Networks

from bot.config import PRICING_PLANS, config, BASE_DEVICES, EXTRA_DEVICE_STARS, PROMO_CODES
from bot.keyboards.inline import (
    get_pricing_keyboard, get_start_options_keyboard, get_plan_list_keyboard,
    get_device_count_keyboard, get_payment_method_keyboard,
)
from bot.keyboards.callbacks import (
    PayPlanCallback, NavCallback, DeviceCountCallback, ConfirmDevicesCallback,
    BackToPlansCallback, PaymentMethodCallback,
)
from bot.services.vpn_panel import VPNPanelService
from bot.utils.xui import add_extra_device
from bot.database.db import db

# Инициализация Crypto Pay с использованием токена из Pydantic-конфига
crypto = AioCryptoPay(token=config.CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)

router = Router()

# ──────────────────────────────────────────────────────────────
# Путь к баннеру
# ──────────────────────────────────────────────────────────────
BANNER_START = "bot/assets/start_banner.png"

# ──────────────────────────────────────────────────────────────
# Хранилища в памяти процесса
# ──────────────────────────────────────────────────────────────
USER_PROMO: dict[int, str] = {}           # user_id -> применённый промокод
GIFT_CODES: dict[str, dict] = {}         # gift_code -> {"days": int, "count": int}
USED_FREE_PROMOS: dict[int, set] = {}    # user_id -> set(кодов free_days)


class PromoStates(StatesGroup):
    waiting_for_code = State()


def _price_for(plan_key: str, count: int) -> int:
    plan = PRICING_PLANS[plan_key]
    extra = max(0, count - BASE_DEVICES)
    total = plan["stars"] + extra * EXTRA_DEVICE_STARS
    return total


def _apply_promo(user_id: int, total: int) -> int:
    code = USER_PROMO.get(user_id)
    if code and code in PROMO_CODES and "discount_stars" in PROMO_CODES[code]:
        total = max(1, total - PROMO_CODES[code]["discount_stars"])
    return total

# --- Безопасное обновление сообщений с поддержкой картинок ---
async def safe_edit_message(callback: types.CallbackQuery, photo_path: str, caption: str, reply_markup=None):
    try:
        if callback.message.photo:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(photo_path),
                    caption=caption,
                    parse_mode="Markdown"
                ),
                reply_markup=reply_markup
            )
        else:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception:
        try:
            await callback.message.answer_photo(
                photo=FSInputFile(photo_path),
                caption=caption,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# ВЫБОР ТАРИФА -> ЭКРАН ВЫБОРА КОЛИЧЕСТВА УСТРОЙСТВ
# ──────────────────────────────────────────────────────────────
@router.callback_query(PayPlanCallback.filter())
async def process_pick_plan(callback: types.CallbackQuery, callback_data: PayPlanCallback):
    plan = PRICING_PLANS.get(callback_data.plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    total = _price_for(callback_data.plan_key, BASE_DEVICES)
    total = _apply_promo(callback.from_user.id, total)

    text = (
        f"📝 **План выбран: {plan['title']}**\n\n"
        f"📱 Устройств в тарифе: {BASE_DEVICES}\n"
        f"➕ Каждое доп. устройство: +{EXTRA_DEVICE_STARS}⭐\n\n"
        f"Выберите нужное количество устройств:\n\n"
        f"💰 Итого: {total}⭐"
    )
    keyboard = get_device_count_keyboard(callback_data.plan_key, callback_data.mode, BASE_DEVICES)
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(DeviceCountCallback.filter())
async def process_pick_device_count(callback: types.CallbackQuery, callback_data: DeviceCountCallback):
    plan = PRICING_PLANS.get(callback_data.plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    total = _price_for(callback_data.plan_key, callback_data.count)
    total = _apply_promo(callback.from_user.id, total)

    text = (
        f"📝 **План выбран: {plan['title']}**\n\n"
        f"📱 Устройств в тарифе: {BASE_DEVICES}\n"
        f"➕ Каждое доп. устройство: +{EXTRA_DEVICE_STARS}⭐\n\n"
        f"Выберите нужное количество устройств:\n\n"
        f"💰 Итого: {total}⭐"
    )
    keyboard = get_device_count_keyboard(callback_data.plan_key, callback_data.mode, callback_data.count)
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(BackToPlansCallback.filter())
async def process_back_to_plans(callback: types.CallbackQuery, callback_data: BackToPlansCallback):
    keyboard = get_plan_list_keyboard(mode=callback_data.mode)
    text = "🚀 **СТАРТУЕМ СЕЙЧАС!**\nВыберите тариф:"
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


# ──────────────────────────────────────────────────────────────
# ПОДТВЕРЖДЕНИЕ КОЛИЧЕСТВА УСТРОЙСТВ -> ВЫБОР СПОСОБА ОПЛАТЫ
# ──────────────────────────────────────────────────────────────
@router.callback_query(ConfirmDevicesCallback.filter())
async def process_confirm_devices(callback: types.CallbackQuery, callback_data: ConfirmDevicesCallback):
    plan = PRICING_PLANS.get(callback_data.plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    total = _price_for(callback_data.plan_key, callback_data.count)
    total_before_promo = total
    total = _apply_promo(callback.from_user.id, total)

    price_line = f"{total}⭐" if total == total_before_promo else f"~~{total_before_promo}⭐~~ {total}⭐ 🎯"

    text = (
        f"📋 **План выбран: {plan['title']}**\n\n"
        f"📅 Длительность: {plan['days']} дн.\n"
        f"🔑 Устройств: {callback_data.count}\n"
        f"💰 Стоимость: {price_line}\n\n"
        f"Выберите удобный способ оплаты:"
    )
    keyboard = get_payment_method_keyboard(callback_data.plan_key, callback_data.mode, callback_data.count)
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(PaymentMethodCallback.filter())
async def process_payment_method(callback: types.CallbackQuery, callback_data: PaymentMethodCallback):
    plan = PRICING_PLANS.get(callback_data.plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    total_stars = _price_for(callback_data.plan_key, callback_data.count)
    total_stars = _apply_promo(callback.from_user.id, total_stars)
    promo_code = USER_PROMO.get(callback.from_user.id, "none")

    # 1. Оплата звёздами ⭐ (Telegram Stars)
    if callback_data.method == "stars":
        payload = f"vpn|{callback_data.mode}|{callback_data.plan_key}|{callback_data.count}|{promo_code}|stars"
        prices = [types.LabeledPrice(label=f"{plan['title']} x{callback_data.count}", amount=total_stars)]
        
        await callback.message.answer_invoice(
            title=f"{plan['title']} — {callback_data.count} устройств",
            description=plan["desc"],
            payload=payload,
            currency="XTR",
            prices=prices,
            provider_token=""
        )
        await callback.answer()
        return

    # 2. Оплата криптовалютой (USDT через CryptoBot) с поддержкой банковских карт
    if callback_data.method == "crypto":
        price_usdt = round(total_stars * 0.02, 2)  # Примерный курс: 1 звезда ≈ 0.02 USDT
        payload = f"vpn|{callback_data.mode}|{callback_data.plan_key}|{callback_data.count}|{promo_code}|crypto"

        try:
            invoice = await crypto.create_invoice(
                asset='USDT',
                amount=price_usdt,
                description=f"{plan['title']} — {callback_data.count} устройств (VPN)",
                payload=payload,
                expires_in=1800
            )

            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="💳 Оплатить картой / USDT", url=invoice.pay_url)],
                [types.InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_crypto_{invoice.invoice_id}")]
            ])

            await safe_edit_message(
                callback, 
                BANNER_START, 
                f"🪙 **Оплата криптовалютой / картой**\n\n"
                f"Сумма к оплате: **{price_usdt} USDT**\n\n"
                f"Нажмите кнопку ниже для безопасной оплаты. Вы можете использовать обычные банковские карты — сервис автоматически конвертирует их в USDT.",
                reply_markup=keyboard
            )
        except Exception as e:
            await callback.answer(f"❌ Ошибка создания счета: {e}", show_alert=True)
            
        await callback.answer()
        return


# ──────────────────────────────────────────────────────────────
# ПРОВЕРКА ОПЛАТЫ КРИПТОГРАФИЧЕСКОГО СЧЕТА (CRYPTOBOT)
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("check_crypto_"))
async def process_check_crypto_payment(callback: types.CallbackQuery):
    invoice_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    username = callback.from_user.username or "User"

    try:
        invoices = await crypto.get_invoices(invoice_ids=invoice_id)
        if not invoices:
            await callback.answer("❌ Счет не найден.", show_alert=True)
            return

        inv = invoices[0]
        if inv.status == "paid":
            payload = inv.payload
            parts = payload.split("|")
            if len(parts) != 6 or parts[0] != "vpn":
                await callback.answer("❌ Ошибка данных платежа.", show_alert=True)
                return

            _, mode, plan_key, count_str, promo_code, _ = parts
            plan = PRICING_PLANS.get(plan_key, {"days": 30})
            days = plan["days"]
            count = int(count_str)

            # Логируем платеж в БД
            await db.add_payment(
                user_id=user_id,
                amount=inv.amount,
                currency="USDT",
                payload=payload,
                charge_id=str(inv.invoice_id)
            )

            if promo_code != "none" and USER_PROMO.get(user_id) == promo_code:
                del USER_PROMO[user_id]

            if mode == "gift":
                gift_code = uuid.uuid4().hex[:10]
                GIFT_CODES[gift_code] = {"days": days, "count": count}
                bot_info = await callback.bot.get_me()
                gift_link = f"https://t.me/{bot_info.username}?start=gift_{gift_code}"
                await callback.message.answer(
                    f"🎉 **Подарочный сертификат готов!**\n\n"
                    f"📅 Срок: {days} дн. · 📱 Устройств: {count}\n\n"
                    f"Перешлите эту ссылку другу:\n`{gift_link}`",
                    parse_mode="Markdown"
                )
                await callback.answer("Оплата подтверждена!", show_alert=True)
                return

            vpn_config = await VPNPanelService.generate_vpn_key(user_id, username, days=days)

            # Реферальный бонус
            user = await db.get_user(user_id)
            if user and user.get("referrer_id"):
                ref_id = user["referrer_id"]
                await VPNPanelService.generate_vpn_key(ref_id, "ReferrerBonus", days=7)
                try:
                    await callback.bot.send_message(ref_id, "🎉 Твой реферал оплатил подписку! Тебе начислено +7 бонусных дней!")
                except Exception:
                    pass

            for _ in range(max(0, count - 1)):
                await add_extra_device(user_id, days=days)

            await db.set_device_limit(user_id, count)

            await callback.message.answer(
                f"🎉 **Оплата прошла успешно! Подписка оформлена на {days} дн.**\n\n"
                f"📱 Устройств: {count}\n"
                f"🔑 **Ключ:**\n`{vpn_config}`",
                parse_mode="Markdown"
            )
            await callback.answer("Успешно!", show_alert=True)
        else:
            await callback.answer("⏳ Оплата еще не поступила. Попробуйте чуть позже.", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка проверки: {e}", show_alert=True)


# ──────────────────────────────────────────────────────────────
# ПРОМОКОД
# ──────────────────────────────────────────────────────────────
@router.callback_query(NavCallback.filter(F.target == "promo_flow"))
async def promo_flow_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PromoStates.waiting_for_code)
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[[
        types.InlineKeyboardButton(text="❌ Отмена", callback_data=NavCallback(target="buy_sub").pack())
    ]])
    text = "🎟 **Введите промокод одним сообщением:**"
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


@router.message(PromoStates.waiting_for_code)
async def promo_flow_apply(message: types.Message, state: FSMContext):
    await state.clear()
    code = message.text.strip().upper()
    user_id = message.from_user.id

    if code not in PROMO_CODES:
        await message.answer("❌ Промокод не найден или уже недействителен.")
        return

    promo = PROMO_CODES[code]

    if "free_days" in promo:
        if code in USED_FREE_PROMOS.get(user_id, set()):
            await message.answer("❌ Вы уже активировали этот промокод ранее.")
            return

        days = promo["free_days"]
        vpn_config = await VPNPanelService.generate_vpn_key(user_id, message.from_user.username or "User", days=days)

        if not vpn_config or not str(vpn_config).startswith("vless://"):
            await message.answer(f"❌ Ошибка активации промокода: {vpn_config}")
            return

        now_ms = int(time.time() * 1000)
        user = await db.get_user(user_id)
        current_expiry = user.get("expiry_time", 0) if user else 0
        base_time = max(current_expiry, now_ms) if current_expiry > now_ms else now_ms
        new_expiry = base_time + days * 24 * 60 * 60 * 1000

        await db.add_or_update_user(
            user_id=user_id,
            username=message.from_user.username or "User",
            email=f"tg_{user_id}",
            expiry_time=new_expiry
        )

        USED_FREE_PROMOS.setdefault(user_id, set()).add(code)

        await message.answer(
            f"🎉 **Промокод {code} активирован!**\n\n"
            f"📅 Начислено дней: {days}\n"
            f"🔑 **Ключ:**\n`{vpn_config}`",
            parse_mode="Markdown"
        )
        return

    USER_PROMO[user_id] = code
    discount = promo["discount_stars"]
    keyboard = get_plan_list_keyboard(mode="new")
    await message.answer(
        f"✅ Промокод **{code}** применён! Скидка {discount}⭐ будет учтена при оплате.\n\nВыберите тариф:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


# ──────────────────────────────────────────────────────────────
# ПОДАРОК
# ──────────────────────────────────────────────────────────────
@router.callback_query(NavCallback.filter(F.target == "gift_flow"))
async def gift_flow_start(callback: types.CallbackQuery):
    text = "🎁 **Купить в подарок**\n\nВыберите тариф — после оплаты вы получите ссылку, которую можно переслать другу."
    keyboard = get_plan_list_keyboard(mode="gift")
    
    await safe_edit_message(callback, BANNER_START, text, reply_markup=keyboard)
    await callback.answer()


async def redeem_gift_code(code: str, user_id: int, username: str) -> str:
    gift = GIFT_CODES.pop(code, None)
    if not gift:
        return "❌ Этот подарочный сертификат не найден или уже был использован."

    vpn_config = await VPNPanelService.generate_vpn_key(user_id, username, days=gift["days"])
    if not vpn_config or not str(vpn_config).startswith("vless://"):
        return f"❌ Ошибка активации подарка: {vpn_config}"

    now_ms = int(time.time() * 1000)
    user = await db.get_user(user_id)
    current_expiry = user.get("expiry_time", 0) if user else 0
    base_time = max(current_expiry, now_ms) if current_expiry > now_ms else now_ms
    new_expiry = base_time + gift["days"] * 24 * 60 * 60 * 1000

    await db.add_or_update_user(
        user_id=user_id,
        username=username,
        email=f"tg_{user_id}",
        expiry_time=new_expiry
    )

    for _ in range(max(0, gift["count"] - 1)):
        await add_extra_device(user_id, days=gift["days"])

    await db.set_device_limit(user_id, gift["count"])

    return (
        f"🎉 **Подарочный сертификат активирован!**\n\n"
        f"📅 Добавлено дней: {gift['days']}\n"
        f"🔑 Ключ:\n`{vpn_config}`"
    )


# ──────────────────────────────────────────────────────────────
# ДОКУПИТЬ ОДНО УСТРОЙСТВО СВЕРХ ЛИМИТА
# ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "buy_extra_device")
async def buy_extra_device_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    expiry_ms = user.get("expiry_time", 0) if user else 0
    now_ms = int(time.time() * 1000)

    if expiry_ms <= now_ms:
        await callback.answer("❌ Для покупки доп. устройства нужна активная подписка!", show_alert=True)
        return

    remaining_days = max(1, -(-(expiry_ms - now_ms) // (24 * 60 * 60 * 1000)))
    payload = f"extradev|{remaining_days}"

    prices = [types.LabeledPrice(label="Доп. устройство", amount=EXTRA_DEVICE_STARS)]
    await callback.message.answer_invoice(
        title="Дополнительное устройство",
        description=f"Новый ключ, действующий до конца текущей подписки ({remaining_days} дн.).",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token=""
    )
    await callback.answer()


@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    username = message.from_user.username or "User"

    if payload.startswith("extradev|"):
        await db.add_payment(
            user_id=user_id,
            amount=payment.total_amount,
            currency=payment.currency,
            payload=payload,
            charge_id=payment.telegram_payment_charge_id
        )

        remaining_days = int(payload.split("|")[1])
        new_key = await add_extra_device(user_id, days=remaining_days)

        if not new_key or not str(new_key).startswith("vless://"):
            await message.answer(f"❌ Оплата прошла, но при создании ключа произошла ошибка: {new_key}. Напишите в поддержку.")
            return

        current_limit = await db.get_device_limit(user_id, default=1)
        await db.set_device_limit(user_id, current_limit + 1)

        await message.answer(
            f"🎉 **Устройство добавлено!**\n\n"
            f"🔑 **Ключ:**\n`{new_key}`",
            parse_mode="Markdown"
        )
        return

    parts = payload.split("|")
    if len(parts) != 6 or parts[0] != "vpn":
        return

    _, mode, plan_key, count_str, promo_code, _ = parts
    plan = PRICING_PLANS.get(plan_key, {"days": 30})
    days = plan["days"]
    count = int(count_str)

    await db.add_payment(
        user_id=user_id,
        amount=payment.total_amount,
        currency=payment.currency,
        payload=payload,
        charge_id=payment.telegram_payment_charge_id
    )

    if promo_code != "none" and USER_PROMO.get(user_id) == promo_code:
        del USER_PROMO[user_id]

    if mode == "gift":
        gift_code = uuid.uuid4().hex[:10]
        GIFT_CODES[gift_code] = {"days": days, "count": count}
        bot_info = await message.bot.get_me()
        gift_link = f"https://t.me/{bot_info.username}?start=gift_{gift_code}"
        await message.answer(
            f"🎉 **Подарочный сертификат готов!**\n\n"
            f"📅 Срок: {days} дн. · 📱 Устройств: {count}\n\n"
            f"Перешлите эту ссылку другу:\n`{gift_link}`",
            parse_mode="Markdown"
        )
        return

    vpn_config = await VPNPanelService.generate_vpn_key(user_id, username, days=days)

    user = await db.get_user(user_id)
    if user and user.get("referrer_id"):
        ref_id = user["referrer_id"]
        await VPNPanelService.generate_vpn_key(ref_id, "ReferrerBonus", days=7)
        try:
            await message.bot.send_message(ref_id, "🎉 Твой реферал оплатил подписку! Тебе начислено +7 бонусных дней!")
        except Exception:
            pass

    for _ in range(max(0, count - 1)):
        await add_extra_device(user_id, days=days)

    await db.set_device_limit(user_id, count)

    await message.answer(
        f"🎉 **Подписка успешно {'продлена' if mode == 'renew' else 'оформлена'} на {days} дн.!**\n\n"
        f"📱 Устройств: {count}\n"
        f"🔑 **Ключ:**\n`{vpn_config}`",
        parse_mode="Markdown"
    )