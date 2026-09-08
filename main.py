import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import config
from templates import CATEGORIES, CATEGORY_LIST

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
storage = MemoryStorage()
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=storage)

# Создаем роутер
router = Router()

# --- Определяем состояния FSM ---
class Form(StatesGroup):
    choosing_category = State()
    filling_fields = State()
    waiting_for_photos = State()

# --- Хранилище временных данных ---
user_data = {}

# --- КНОПКИ ---
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton("❌ ОТМЕНА")]], resize_keyboard=True
)

done_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("✅ ГОТОВО (опубликовать)")],
        [KeyboardButton("❌ ОТМЕНА")]
    ], resize_keyboard=True
)

main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton("🚀 ЗАПУСТИТЬ БОТА")]], resize_keyboard=True
)

# --- ФУНКЦИЯ ВОЗВРАТА В МЕНЮ ---
async def return_to_main_menu(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in user_data:
        user_data.pop(message.from_user.id)
    await message.answer(
        "🏠 Возвращаемся в главное меню!\n\nНажми кнопку ниже, чтобы начать заново:",
        reply_markup=main_menu_keyboard
    )

# --- /start ---
@router.message(Command('start'))
async def start_command(message: Message):
    await message.answer(
        "👋 Привет! Я бот для создания объявлений!\n\n"
        "📌 Нажми на кнопку ниже, чтобы выбрать категорию товара:",
        reply_markup=main_menu_keyboard
    )

# --- КНОПКА ЗАПУСКА ---
@router.message(F.text == "🚀 ЗАПУСТИТЬ БОТА")
async def start_bot_button(message: Message, state: FSMContext):
    await state.clear()
    if message.from_user.id in user_data:
        user_data.pop(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for key in CATEGORY_LIST:
        category = CATEGORIES[key]
        keyboard.add(InlineKeyboardButton(category["name"], callback_data=f"cat_{key}"))

    await message.answer("📋 Выбери категорию товара:", reply_markup=keyboard)
    await state.set_state(Form.choosing_category)

# --- ОТМЕНА ---
@router.message(F.text == "❌ ОТМЕНА")
async def cancel_button_handler(message: Message, state: FSMContext):
    await return_to_main_menu(message, state)

# --- ГОТОВО ---
@router.message(F.text == "✅ ГОТОВО (опубликовать)", StateFilter(Form.waiting_for_photos))
async def done_photos_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Ошибка. Начни заново /start")
        await state.clear()
        return
    
    photos = data.get("photos", [])
    if not photos:
        await message.answer("⚠️ Ты не загрузил ни одного фото!\n\n📸 Отправь хотя бы одно фото.", reply_markup=cancel_keyboard)
        return
    
    category_key = data["category"]
    category = CATEGORIES[category_key]
    filled_fields = data["fields"]
    
    if "price" not in filled_fields or not filled_fields["price"]:
        filled_fields["price"] = "—"
    if "avito_link" not in filled_fields or not filled_fields["avito_link"]:
        filled_fields["avito_link"] = "#"
    
    filled_fields["tags"] = category.get("tags", "")
    
    try:
        final_text = category["template"].format(**filled_fields)
    except KeyError as e:
        await message.answer(f"⚠️ Ошибка в шаблоне: не хватает поля {e}")
        await state.clear()
        return
    
    try:
        if len(photos) == 1:
            await bot.send_photo(chat_id=config.CHANNEL_ID, photo=photos[0], caption=final_text, parse_mode="HTML")
        else:
            media_group = []
            for i, photo_id in enumerate(photos):
                if i == 0:
                    media_group.append(InputMediaPhoto(media=photo_id, caption=final_text, parse_mode="HTML"))
                else:
                    media_group.append(InputMediaPhoto(media=photo_id))
            await bot.send_media_group(chat_id=config.CHANNEL_ID, media=media_group)
        
        await message.answer("✅ ГОТОВО! Объявление опубликовано! 🎉", reply_markup=main_menu_keyboard)
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при отправке: {e}\n\nПроверь:\n1. Бот админ в канале\n2. CHANNEL_ID правильный\n3. Права на отправку",
            reply_markup=main_menu_keyboard
        )
    
    user_data.pop(user_id, None)
    await state.clear()

# --- ВЫБОР КАТЕГОРИИ ---
@router.callback_query(F.data.startswith('cat_'), StateFilter(Form.choosing_category))
async def process_category(callback_query: CallbackQuery, state: FSMContext):
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

    await callback_query.answer()
    await callback_query.message.answer(
        f"📝 Начинаем заполнение для категории *{category['name']}*\n\n"
        f"Вопрос 1 из {len(fields)}:\n{first_question}\n\n"
        f"✏️ Просто напиши ответ в чат:",
        parse_mode="Markdown", reply_markup=cancel_keyboard
    )
    await state.set_state(Form.filling_fields)

# --- ОТВЕТЫ НА ВОПРОСЫ ---
@router.message(StateFilter(Form.filling_fields))
async def process_field_answer(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Что-то пошло не так. Начни заново /start")
        await state.clear()
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
            f"✅ Принято!\n\nВопрос {next_index + 1} из {len(fields)}:\n{next_question}\n\n✏️ Напиши ответ:",
            reply_markup=cancel_keyboard
        )
    else:
        await message.answer(
            "✅ Отлично! Все характеристики заполнены.\n\n📸 Теперь отправь ФОТО товара.\n• Можно до 4 фото\n• Отправляй по одному\n• Когда загрузишь все — нажми 'ГОТОВО'",
            reply_markup=done_keyboard
        )
        await state.set_state(Form.waiting_for_photos)

# --- ФОТО ---
@router.message(StateFilter(Form.waiting_for_photos), F.photo)
async def process_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = user_data.get(user_id)
    
    if not data:
        await message.answer("⚠️ Ошибка. Начни заново /start")
        await state.clear()
        return
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    if "photos" not in data:
        data["photos"] = []
    
    if len(data["photos"]) >= 4:
        await message.answer("⚠️ Ты уже загрузил 4 фото! Максимум 4.\n\nНажми '✅ ГОТОВО (опубликовать)'", reply_markup=done_keyboard)
        return
    
    data["photos"].append(file_id)
    remaining = 4 - len(data["photos"])
    
    await message.answer(f"✅ Фото {len(data['photos'])} загружено!\n\n📸 Осталось: {remaining} фото\n• Отправь еще или нажми 'ГОТОВО'", reply_markup=done_keyboard)

# --- НЕ ФОТО ---
@router.message(StateFilter(Form.waiting_for_photos), ~F.photo)
async def wrong_photo_input(message: Message, state: FSMContext):
    if message.text in ["✅ ГОТОВО (опубликовать)", "❌ ОТМЕНА"]:
        return
    await message.answer("⚠️ Пожалуйста, отправь именно ФОТО (картинку).\n\n📸 Нажми на скрепку 📎 и выбери фото.\n\nИли нажми 'ГОТОВО'.", reply_markup=done_keyboard)

# --- /cancel ---
@router.message(Command('cancel'))
async def cancel_command(message: Message, state: FSMContext):
    await return_to_main_menu(message, state)

# --- /help ---
@router.message(Command('help'))
async def help_command(message: Message):
    await message.answer(
        "🤖 Как пользоваться ботом:\n"
        "1️⃣ Нажми '🚀 ЗАПУСТИТЬ БОТА'\n"
        "2️⃣ Выбери категорию\n"
        "3️⃣ Отвечай на вопросы\n"
        "4️⃣ Отправь до 4 фото\n"
        "5️⃣ Нажми 'ГОТОВО'\n"
        "6️⃣ Готово! 🎉\n\n"
        "❌ На любом этапе можно нажать 'ОТМЕНА'"
    )

# Регистрируем роутер
dp.include_router(router)

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("🤖 БОТ ЗАПУЩЕН И ГОТОВ К РАБОТЕ!")
    import asyncio
    asyncio.run(dp.start_polling(bot))
