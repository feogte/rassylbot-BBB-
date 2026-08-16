import asyncio
import json
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telethon import TelegramClient, events
from telethon.errors import PasswordHashInvalidError, PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError

API_ID = 34396100
API_HASH = "d33db4d069ee51341b12b9d95fc5282d"

BOT_TOKEN = "8869528592:AAEEHw7E0an-LDrm4Fz3Qe4z7SqraFO2W_w"
OWNER_ID = 8634266032
PHONE_NUMBER = "+79046779804"

DEFAULT_SOURCE = -1004328683164
DEFAULT_TARGET = -1003970374690

SESSION_NAME = "forward_session"
ROUTES_FILE = Path("routes.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
tg = TelegramClient(SESSION_NAME, API_ID, API_HASH)

class AddRoute(StatesGroup):
    source = State()
    target = State()

class Login(StatesGroup):
    code = State()
    password = State()

def load_routes():
    if not ROUTES_FILE.exists():
        return [{"source": DEFAULT_SOURCE, "target": DEFAULT_TARGET}]
    try:
        data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logging.exception("routes.json read error")
        return []

def save_routes():
    ROUTES_FILE.write_text(json.dumps(routes, ensure_ascii=False, indent=2), encoding="utf-8")

routes = load_routes()
phone_code_hash = None

def owner(user_id):
    return user_id == OWNER_ID

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пересылку", callback_data="add")],
        [InlineKeyboardButton(text="📋 Мои пересылки", callback_data="list")],
        [InlineKeyboardButton(text="🗑 Удалить пересылку", callback_data="delete")],
        [InlineKeyboardButton(text="🔐 Статус Telegram", callback_data="status")],
    ])

def back():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]
    ])

def delete_menu():
    buttons = [
        [InlineKeyboardButton(text=f"❌ {r['source']} → {r['target']}", callback_data=f"del:{i}")]
        for i, r in enumerate(routes)
    ]
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def routes_text():
    if not routes:
        return "📋 <b>Пересылок нет.</b>"
    text = "📋 <b>Активные пересылки:</b>\n\n"
    for i, r in enumerate(routes, 1):
        text += f"{i}. <code>{r['source']}</code> → <code>{r['target']}</code>\n"
    return text

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not owner(message.from_user.id):
        return
    if not await tg.is_user_authorized():
        global phone_code_hash
        try:
            await tg.connect()
            sent = await tg.send_code_request(PHONE_NUMBER)
            phone_code_hash = sent.phone_code_hash
        except Exception as e:
            await message.answer(f"❌ Не удалось отправить код Telegram:\n<code>{e}</code>")
            return
        await state.set_state(Login.code)
        await message.answer(
            f"🔐 Код отправлен на <code>{PHONE_NUMBER}</code>.\n\n"
            "Отправь код из Telegram сюда."
        )
        return
    await state.clear()
    await message.answer("🤖 <b>Управление пересылками</b>\n\nВыбери действие:", reply_markup=menu())

@dp.message(Login.code)
async def login_code(message: Message, state: FSMContext):
    if not owner(message.from_user.id):
        return
    code = (message.text or "").strip().replace(" ", "")
    try:
        await tg.sign_in(phone=PHONE_NUMBER, code=code, phone_code_hash=phone_code_hash)
        await state.clear()
        await message.answer("✅ <b>Telegram-аккаунт авторизован.</b>", reply_markup=menu())
    except SessionPasswordNeededError:
        await state.set_state(Login.password)
        await message.answer("🔒 Введи пароль двухэтапной аутентификации Telegram.")
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуй ещё раз.")
    except PhoneCodeExpiredError:
        await state.clear()
        await message.answer("❌ Код истёк. Отправь /start для нового кода.")
    except Exception as e:
        await state.clear()
        logging.exception("login error")
        await message.answer(f"❌ Ошибка авторизации:\n<code>{e}</code>")

@dp.message(Login.password)
async def login_password(message: Message, state: FSMContext):
    if not owner(message.from_user.id):
        return
    try:
        await tg.sign_in(password=message.text or "")
        await state.clear()
        await message.answer("✅ <b>Telegram-аккаунт авторизован.</b>", reply_markup=menu())
    except PasswordHashInvalidError:
        await message.answer("❌ Неверный пароль 2FA. Попробуй ещё раз.")
    except Exception as e:
        await state.clear()
        logging.exception("2FA error")
        await message.answer(f"❌ Ошибка авторизации:\n<code>{e}</code>")

@dp.callback_query(F.data == "menu")
async def menu_handler(c: CallbackQuery, state: FSMContext):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await c.message.edit_text("🤖 <b>Управление пересылками</b>\n\nВыбери действие:", reply_markup=menu())
    await c.answer()

@dp.callback_query(F.data == "status")
async def status(c: CallbackQuery):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    ok = await tg.is_user_authorized()
    text = "🟢 <b>Telegram подключён.</b>" if ok else "🔴 <b>Telegram не авторизован.</b>"
    await c.message.edit_text(text, reply_markup=back())
    await c.answer()

@dp.callback_query(F.data == "add")
async def add(c: CallbackQuery, state: FSMContext):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    if not await tg.is_user_authorized():
        await c.answer("Сначала авторизуй Telegram-аккаунт через /start.", show_alert=True)
        return
    await state.set_state(AddRoute.source)
    await c.message.edit_text(
        "➕ <b>Добавление пересылки</b>\n\nОтправь ID канала-источника:\n<code>-1001234567890</code>",
        reply_markup=back()
    )
    await c.answer()

@dp.message(AddRoute.source)
async def source(message: Message, state: FSMContext):
    if not owner(message.from_user.id):
        return
    try:
        value = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("❌ ID должен быть числом.")
        return
    await state.update_data(source=value)
    await state.set_state(AddRoute.target)
    await message.answer(
        "Теперь отправь ID чата-получателя:\n<code>-1001234567890</code>",
        reply_markup=back()
    )

@dp.message(AddRoute.target)
async def target(message: Message, state: FSMContext):
    if not owner(message.from_user.id):
        return
    try:
        value = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer("❌ ID должен быть числом.")
        return
    data = await state.get_data()
    route = {"source": data["source"], "target": value}
    if route in routes:
        await state.clear()
        await message.answer("⚠️ Такая пересылка уже существует.", reply_markup=menu())
        return
    routes.append(route)
    save_routes()
    await state.clear()
    await message.answer(
        f"✅ <b>Добавлено</b>\n\nКанал: <code>{route['source']}</code>\nЧат: <code>{route['target']}</code>",
        reply_markup=menu()
    )

@dp.callback_query(F.data == "list")
async def list_routes(c: CallbackQuery):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    await c.message.edit_text(routes_text(), reply_markup=back())
    await c.answer()

@dp.callback_query(F.data == "delete")
async def delete_routes(c: CallbackQuery):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    await c.message.edit_text(
        "🗑 <b>Выбери пересылку для удаления:</b>" if routes else "🗑 <b>Пересылок нет.</b>",
        reply_markup=delete_menu() if routes else back()
    )
    await c.answer()

@dp.callback_query(F.data.startswith("del:"))
async def delete_route(c: CallbackQuery):
    if not owner(c.from_user.id):
        await c.answer("Нет доступа.", show_alert=True)
        return
    i = int(c.data.split(":")[1])
    if i >= len(routes):
        await c.answer("Уже удалено.", show_alert=True)
        return
    removed = routes.pop(i)
    save_routes()
    await c.message.edit_text(
        f"✅ Удалено:\n<code>{removed['source']}</code> → <code>{removed['target']}</code>",
        reply_markup=menu()
    )
    await c.answer()

@tg.on(events.NewMessage)
async def new_message(event):
    chat_id = event.chat_id
    if chat_id is None:
        return
    matches = [r for r in routes if r["source"] == chat_id]
    for route in matches:
        try:
            target = await tg.get_entity(route["target"])
            source_entity = await tg.get_entity(route["source"])
            await tg.forward_messages(target, event.message, from_peer=source_entity)
            logging.info("Forwarded %s -> %s, message=%s", route["source"], route["target"], event.message.id)
        except Exception:
            logging.exception("Forward error %s -> %s", route["source"], route["target"])

async def main():
    await tg.connect()
    logging.info("Telegram authorized: %s", await tg.is_user_authorized())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
