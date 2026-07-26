from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

from bot.utils.ai_helper import ask_ai_support

router = Router()

class SupportStates(StatesGroup):
    chatting_with_ai = State()

# Главное меню поддержки с кнопкой ИИ
def get_support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Задать вопрос ИИ-помощнику", callback_data="start_ai_support")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_home")]
    ])

# 🛠 Ловим любые варианты callback_data, содержащие слова support или help
@router.callback_query(F.data.contains("support") | (F.data == "help"))
async def support_menu_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🛠 **ТЕХНИЧЕСКАЯ ПОДДЕРЖКА**\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "Возникли вопросы по настройке или подключению VPN?\n"
        "Наш умный ИИ-помощник готов помочь вам прямо здесь 24/7!"
    )
    await callback.message.edit_text(text, reply_markup=get_support_keyboard(), parse_mode="Markdown")
    await callback.answer()

# Кнопка запуска чата с ИИ
@router.callback_query(F.data == "start_ai_support")
async def start_ai_chat(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.chatting_with_ai)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Завершить диалог", callback_data="stop_ai_support")
    ]])
    
    await callback.message.edit_text(
        "🤖 **ИИ-помощник на связи!**\n\n"
        "Напишите свой вопрос в чат (например: *«Какое приложение скачать на iPhone?»* или *«Как импортировать ключ?»*), и я сразу отвечу.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

# Обработка текстовых вопросов пользователя к ИИ
@router.message(SupportStates.chatting_with_ai)
async def process_ai_dialog(message: Message, state: FSMContext):
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    ai_response = await ask_ai_support(message.text)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Завершить диалог", callback_data="stop_ai_support")
    ]])
    
    await message.answer(ai_response, reply_markup=keyboard, parse_mode="Markdown")

# Кнопка выхода из чата с ИИ
@router.callback_query(F.data == "stop_ai_support")
async def stop_ai_chat(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "✅ Диалог с поддержкой завершен.",
        reply_markup=get_support_keyboard()
    )
    await callback.answer()