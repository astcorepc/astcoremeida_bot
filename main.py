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
    waiting_for_photos = State()


# --- Хранилище временных данных ---
user_data = {}


# --- КНОПКА "ОТМЕНА" ---
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("❌ ОТМЕНА")]
    ],
    resize_keyboard=True
)

# --- КНОПКА "ГОТОВО" ---
done_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("✅ ГОТОВО (опубликовать)")],
        [KeyboardButton("❌ ОТМЕНА")]
    ],
    resize_keyboard=True
)

# --- КНОПКА "ГЛАВНОЕ МЕНЮ" ---
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]
    ],
    resize_keyboard=True
)


# --- ФУНКЦИЯ ВОЗВРАТА В ГЛАВНОЕ МЕНЮ ---
async def return_to_main_menu(message: types.Message, state: FSMContext):
    await state.finish()
    if message.from_user.id in user_data:
        user_data.pop(message.from_user.id)
    
    await message.answer(
        "🏠 Возвращаемся в главное меню!\n\n"
        "Нажми кнопку ниже, чтобы начать заново:",
        reply_markup=main_menu_keyboard
    )


# --- КОМАНДА /start ---
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для создания объявлений в твой канал!\n\n"
        "📌 Нажми на кнопку ниже, чтобы выбрать категорию товара:",
        reply_markup=main_menu_keyboard
    )


# --- ОБРАБОТЧИК КНОПКИ "ЗАПУСТИТЬ БОТА" ---
@dp.message_handler(lambda message: message.text == "🚀 ЗАПУСТИТЬ БОТА")
async def start_bot_button(message: types.Message, state: FSMContext):
    await state.finish()
    if message.from_user.id in user_data:
        user_data.pop(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key in CATEGORY_LIST:
        category = CATEGORIES[key]
        keyboard.insert(InlineKeyboardButton(category["name"], callback_data=f"cat_{key}"))

    await message.answer(
        "📋 Выбери категорию товара:",
        reply_markup=keyboard
    )
    await Form.choosing_category.set()


# --- ОБРАБОТЧИК КНОПКИ "ОТМЕНА" ---
@dp.message_handler(lambda message: message.text == "❌ ОТМЕНА", state='*')
async def cancel_button_handler(message: types.Message, state: FSMContext):
    await return_to_main_menu(message, state)


# --- ОБРАБОТЧИК КНОПКИ "ГОТОВО" ---
@dp.message_handler(lambda message: message.text == "✅ ГОТОВО (опубликовать)", state=Form.waiting_for_photos)
async def done_photos_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Ошибка. Начни заново /start")
        await state.finish()
        return
    
    photos = data.get("photos", [])
    
    if not photos:
        await message.answer(
            "⚠️ Ты не загрузил ни одного фото!\n\n"
            "📸 Отправь хотя бы одно фото.",
            reply_markup=cancel_keyboard
        )
        return
    
    # Генерируем текст
    category_key = data["category"]
    category = CATEGORIES[category_key]
    filled_fields = data["fields"]
    
    if "price" not in filled_fields or not filled_fields["price"]:
        filled_fields["price"] = "—"
    
    if "avito_link" not in filled_fields or not filled_fields["avito_link"]:
        filled_fields["avito_link"] = "#"
    
    # ← ЭТА СТРОКА ДОБАВЛЯЕТ ТЕГИ!
    filled_fields["tags"] = category.get("tags", "")
    
    try:
        final_text = category["template"].format(**filled_fields)
    except KeyError as e:
        await message.answer(f"⚠️ Ошибка в шаблоне: не хватает поля {e}")
        await state.finish()
        return
    
    # Отправляем в канал
    try:
        if len(photos) == 1:
            await bot.send_photo(
                chat_id=config.CHANNEL_ID,
                photo=photos[0],
                caption=final_text,
                parse_mode="HTML"
            )
        else:
            from aiogram.types import InputMediaPhoto
            media_group = []
            for i, photo_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo_id, caption=final_text, parse_mode="HTML"))
                else:
                    media_group.append(InputMediaPhoto(media=photo_id))
            
            await bot.send_media_group(
                chat_id=config.CHANNEL_ID,
                media=media_group
            )
        
        await message.answer(
            f"✅ ГОТОВО! Объявление опубликовано в канале! 🎉\n\n"
            f"📸 Загружено фото: {len(photos)} шт.\n\n"
            f"Хочешь создать еще одно? Нажми кнопку ниже:",
            reply_markup=main_menu_keyboard
        )
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при отправке в канал: {e}\n\n"
            f"Проверь:\n"
            f"1. Бот добавлен в канал как администратор\n"
            f"2. CHANNEL_ID правильный (с минусом)\n"
            f"3. У бота есть права на отправку сообщений",
            reply_markup=main_menu_keyboard
        )
    
    user_data.pop(user_id, None)
    await state.finish()


# --- Обработка выбора категории ---
@dp.callback_query_handler(lambda c: c.data.startswith('cat_'), state=Form.choosing_category)
async def process_category(callback_query: types.CallbackQuery, state: FSMContext):
    category_key = callback_query.data.split('_')[1]
    category = CATEGORIES[category_key]

    user_data[callback_query.from_user.id] = {
        "category": category_key,
        "fields": {},
        "field_index": 0,
        "photos": []
    }

    fields = category["fields"]
    first_question = fields[0]["question"]

    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        f"📝 Начинаем заполнение для категории *{category['name']}*\n\n"
        f"Вопрос 1 из {len(fields)}:\n{first_question}\n\n"
        f"✏️ Просто напиши ответ в чат:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard
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

    current_field_key = fields[current_index]["key"]
    data["fields"][current_field_key] = message.text.strip()

    next_index = current_index + 1

    if next_index < len(fields):
        data["field_index"] = next_index
        next_question = fields[next_index]["question"]
        await message.answer(
            f"✅ Принято!\n\n"
            f"Вопрос {next_index + 1} из {len(fields)}:\n"
            f"{next_question}\n\n"
            f"✏️ Напиши ответ:",
            reply_markup=cancel_keyboard
        )
    else:
        await message.answer(
            "✅ Отлично! Все характеристики заполнены.\n\n"
            "📸 Теперь отправь ФОТО товара.\n"
            "• Можно отправить до 4 фото\n"
            "• Отправляй по одному фото\n"
            "• Когда загрузишь все фото — нажми 'ГОТОВО'\n\n"
            "📎 Нажми на скрепку и выбери фото:",
            reply_markup=done_keyboard
        )
        await Form.waiting_for_photos.set()


# --- Обработка фото ---
@dp.message_handler(content_types=['photo'], state=Form.waiting_for_photos)
async def process_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Ошибка. Начни заново /start")
        await state.finish()
        return
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    if "photos" not in data:
        data["photos"] = []
    
    if len(data["photos"]) >= 4:
        await message.answer(
            "⚠️ Ты уже загрузил 4 фото! Максимум 4.\n\n"
            "Если хочешь опубликовать — нажми '✅ ГОТОВО (опубликовать)'",
            reply_markup=done_keyboard
        )
        return
    
    data["photos"].append(file_id)
    remaining = 4 - len(data["photos"])
    
    await message.answer(
        f"✅ Фото {len(data['photos'])} загружено!\n\n"
        f"📸 Осталось места: {remaining} фото\n"
        f"• Отправь еще фото\n"
        f"• Или нажми 'ГОТОВО' для публикации",
        reply_markup=done_keyboard
    )


# --- Обработчик, если отправили не фото ---
@dp.message_handler(state=Form.waiting_for_photos, content_types=['text', 'document', 'video', 'audio', 'sticker', 'animation'])
async def wrong_photo_input(message: types.Message):
    if message.text == "✅ ГОТОВО (опубликовать)":
        return
    if message.text == "❌ ОТМЕНА":
        return
    
    await message.answer(
        "⚠️ Пожалуйста, отправь именно ФОТО (картинку).\n\n"
        "📸 Нажми на скрепку 📎 и выбери фото из галереи.\n\n"
        "Или нажми 'ГОТОВО', если загрузил все фото.",
        reply_markup=done_keyboard
    )


# --- Команда /cancel ---
@dp.message_handler(commands=['cancel'], state='*')
async def cancel_command(message: types.Message, state: FSMContext):
    await return_to_main_menu(message, state)


# --- Команда /help ---
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.answer(
        "🤖 Как пользоваться ботом:\n\n"
        "1️⃣ Нажми '🚀 ЗАПУСТИТЬ БОТА'\n"
        "2️⃣ Выбери категорию товара\n"
        "3️⃣ Отвечай на вопросы\n"
        "4️⃣ Отправь до 4 фото (по одному)\n"
        "5️⃣ Нажми 'ГОТОВО' для публикации\n"
        "6️⃣ Готово! Объявление в канале! 🎉\n\n"
        "📌 Команды:\n"
        "/start - начать работу\n"
        "/cancel - отменить\n"
        "/help - помощь\n\n"
        "❌ На любом этапе можно нажать кнопку 'ОТМЕНА'"
    )


# --- Запуск бота ---
if __name__ == "__main__":
    from aiogram import executor
    print("🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    executor.start_polling(dp, skip_updates=True)
