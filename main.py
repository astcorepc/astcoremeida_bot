import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import os

# ===== НАСТРОЙКИ =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден!")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ===== КНОПКА СТАРТ =====
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]
    ],
    resize_keyboard=True
)

# ===== КОМАНДА /start =====
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для создания объявлений!\n\n"
        "Нажми кнопку ниже, чтобы начать:",
        reply_markup=start_keyboard
    )
    print(f"✅ Пользователь {message.from_user.id} нажал /start")

# ===== КНОПКА "ЗАПУСТИТЬ БОТА" =====
@dp.message_handler(lambda message: message.text == "🚀 ЗАПУСТИТЬ БОТА")
async def start_bot_button(message: types.Message):
    await message.answer(
        "✅ Бот работает!\n\n"
        "Выбери категорию товара:",
        reply_markup=InlineKeyboardMarkup(row_width=2)
        .add(
            InlineKeyboardButton("🖥 Процессор", callback_data="cpu"),
            InlineKeyboardButton("🎮 Видеокарта", callback_data="gpu"),
            InlineKeyboardButton("🖥 Корпус", callback_data="case"),
            InlineKeyboardButton("💽 HDD", callback_data="hdd"),
            InlineKeyboardButton("⚡ SSD", callback_data="ssd"),
            InlineKeyboardButton("🧠 Оперативная память", callback_data="ram"),
            InlineKeyboardButton("🔌 Материнская плата", callback_data="motherboard"),
            InlineKeyboardButton("🔋 Блок питания", callback_data="psu")
        )
    )
    print(f"✅ Пользователь {message.from_user.id} нажал кнопку запуска")

# ===== ОБРАБОТКА КНОПОК КАТЕГОРИЙ =====
@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"✅ Выбрана категория: {callback_query.data}\n\n"
        f"📝 Сейчас я задам тебе несколько вопросов.\n"
        f"Просто пиши ответы в чат."
    )
    print(f"✅ Пользователь выбрал категорию: {callback_query.data}")

# ===== ЭХО (для теста) =====
@dp.message_handler()
async def echo(message: types.Message):
    await message.answer(f"📩 Ты написал: {message.text}\n\nНажми /start чтобы начать заново.")
    print(f"📩 Сообщение от {message.from_user.id}: {message.text}")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    from aiogram import executor
    print("🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    print(f"📌 Токен: {BOT_TOKEN[:10]}...")
    executor.start_polling(dp, skip_updates=True)
