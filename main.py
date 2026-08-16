import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import config
from templates import CATEGORIES, CATEGORY_LIST

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


# --- Определяем состояния FSM ---
class Form(StatesGroup):
    choosing_category = State()
    filling_fields = State()
    waiting_for_photo = State()


# --- Хранилище временных данных ---
user_data = {}


# --- КОМАНДА /start С КНОПКОЙ ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    # СОЗДАЕМ КНОПКУ СТАРТ (физическая кнопка внизу)
    start_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "👋 Привет! Я бот для создания объявлений в твой канал!\n\n"
        "📌 Нажми на кнопку ниже, чтобы выбрать категорию товара:",
        reply_markup=start_keyboard
    )


# --- ОБРАБОТЧИК КНОПКИ "ЗАПУСТИТЬ БОТА" ---
@dp.message_handler(lambda message: message.text == "🚀 ЗАПУСТИТЬ БОТА")
async def start_bot_button(message: types.Message):
    # Создаем кнопки с категориями
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key in CATEGORY_LIST:
        category = CATEGORIES[key]
        keyboard.insert(InlineKeyboardButton(category["name"], callback_data=f"cat_{key}"))

    await message.answer(
        "📋 Выбери категорию товара:",
        reply_markup=keyboard
    )
    await Form.choosing_category.set()


# --- Обработка выбора категории ---
@dp.callback_query_handler(lambda c: c.data.startswith('cat_'), state=Form.choosing_category)
async def process_category(callback_query: types.CallbackQuery, state: FSMContext):
    category_key = callback_query.data.split('_')[1]
    category = CATEGORIES[category_key]

    # Сохраняем данные
    user_data[callback_query.from_user.id] = {
        "category": category_key,
        "fields": {},
        "field_index": 0
    }

    fields = category["fields"]
    first_question = fields[0]["question"]

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"📝 Начинаем заполнение для категории *{category['name']}*\n\n"
        f"Вопрос 1 из {len(fields)}:\n{first_question}\n\n"
        f"✏️ Просто напиши ответ в чат:",
        parse_mode="Markdown"
    )
    await Form.filling_fields.set()


# --- Обработка ответов на вопросы ---
@dp.message_handler(state=Form.filling_fields)
async def process_field_answer(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Что-то пошло не так. Начни заново командой /start")
        await state.finish()
        return

    category_key = data["category"]
    category = CATEGORIES[category_key]
    fields = category["fields"]
    current_index = data["field_index"]

    # Сохраняем ответ
    current_field_key = fields[current_index]["key"]
    data["fields"][current_field_key] = message.text.strip()

    next_index = current_index + 1

    if next_index < len(fields):
        # Есть еще вопросы
        data["field_index"] = next_index
        next_question = fields[next_index]["question"]
        await message.answer(
            f"✅ Принято!\n\n"
            f"Вопрос {next_index + 1} из {len(fields)}:\n"
            f"{next_question}\n\n"
            f"✏️ Напиши ответ:"
        )
    else:
        # Все вопросы заданы
        await message.answer(
            "✅ Отлично! Все характеристики заполнены.\n\n"
            "📸 Теперь отправь ФОТО товара.\n"
            "Просто нажми на скрепку 📎 и выбери фото:"
        )
        await Form.waiting_for_photo.set()


# --- Обработка фото ---
@dp.message_handler(content_types=['photo'], state=Form.waiting_for_photo)
async def process_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Ошибка. Начни заново /start")
        await state.finish()
        return

    # Получаем фото
    photo = message.photo[-1]
    file_id = photo.file_id

    # Генерируем текст
    category_key = data["category"]
    category = CATEGORIES[category_key]
    filled_fields = data["fields"]

    # Если цена не указана
    if "price" not in filled_fields or not filled_fields["price"]:
        filled_fields["price"] = "—"

    # Подставляем в шаблон
    try:
        final_text = category["template"].format(**filled_fields)
    except KeyError as e:
        await message.answer(f"⚠️ Ошибка в шаблоне: не хватает поля {e}")
        await state.finish()
        return

    # Отправляем в канал
    try:
        await bot.send_photo(
            chat_id=config.CHANNEL_ID,
            photo=file_id,
            caption=final_text,
            parse_mode="HTML"
        )
        
        # Возвращаем кнопку "Запустить" после успешной публикации
        start_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "✅ ГОТОВО! Объявление опубликовано в канале! 🎉\n\n"
            "Хочешь создать еще одно? Нажми кнопку ниже:",
            reply_markup=start_keyboard
        )
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при отправке в канал: {e}\n\n"
            f"Проверь:\n"
            f"1. Бот добавлен в канал как администратор\n"
            f"2. CHANNEL_ID правильный (с минусом)\n"
            f"3. У бота есть права на отправку сообщений"
        )

    # Очищаем данные
    user_data.pop(user_id, None)
    await state.finish()


# --- Обработчик, если отправили не фото ---
@dp.message_handler(state=Form.waiting_for_photo, content_types=['text', 'document', 'video', 'audio', 'sticker'])
async def wrong_photo_input(message: types.Message):
    await message.answer(
        "⚠️ Пожалуйста, отправь именно ФОТО (картинку).\n\n"
        "📸 Нажми на скрепку 📎 и выбери фото из галереи."
    )


# --- Команда /cancel ---
@dp.message_handler(commands=['cancel'], state='*')
async def cancel_command(message: types.Message, state: FSMContext):
    await state.finish()
    start_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        "❌ Действие отменено.\n\n"
        "Нажми кнопку, чтобы начать заново:",
        reply_markup=start_keyboard
    )


# --- Команда /help ---
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.answer(
        "🤖 Как пользоваться ботом:\n\n"
        "1️⃣ Нажми 'ЗАПУСТИТЬ БОТА'\n"
        "2️⃣ Выбери категорию товара\n"
        "3️⃣ Отвечай на вопросы\n"
        "4️⃣ Отправь фото\n"
        "5️⃣ Готово! Объявление в канале! 🎉\n\n"
        "📌 Команды:\n"
        "/start - начать работу\n"
        "/cancel - отменить\n"
        "/help - помощь"
    )


# --- Запуск бота ---
if __name__ == "__main__":
    from aiogram import executor
    print("🤖 БОТ ЗАПУЩЕН! Напиши ему /start в Telegram")
    executor.start_polling(dp, skip_updates=True)
