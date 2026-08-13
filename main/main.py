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

BOT_TOKEN = "8615096995:AAGIep-U5ZYgzZW02e-qyWpxUs_3_2YXF7Y"
OWNER_ID = 8872934046

DEFAULT_SOURCE_CHANNEL_ID = -1004328683164
DEFAULT_TARGET_CHAT_ID = -1003970374690

ROUTES_FILE = Path("routes.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher(storage=MemoryStorage())


class AddRoute(StatesGroup):
    source = State()
    target = State()


def load_routes():
    if not ROUTES_FILE.exists():
        return [{
            "source": DEFAULT_SOURCE_CHANNEL_ID,
            "target": DEFAULT_TARGET_CHAT_ID,
        }]

    try:
        data = json.loads(ROUTES_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        logging.exception("Ошибка чтения routes.json")
        return []


def save_routes():
    ROUTES_FILE.write_text(
        json.dumps(routes, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


routes = load_routes()


def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить пересылку", callback_data="add_route")],
            [InlineKeyboardButton(text="Мои пересылки", callback_data="list_routes")],
            [InlineKeyboardButton(text="Удалить пересылку", callback_data="delete_route")],
        ]
    )


def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
        ]
    )


def delete_keyboard():
    buttons = [
        [
            InlineKeyboardButton(
                text=f"❌ {route['source']} → {route['target']}",
                callback_data=f"delete:{index}",
            )
        ]
        for index, route in enumerate(routes)
    ]

    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def routes_text():
    if not routes:
        return "📋 <b>Активных пересылок нет.</b>"

    text = "📋 <b>Активные пересылки:</b>\n\n"

    for index, route in enumerate(routes, 1):
        text += (
            f"<b>{index}.</b> "
            f"<code>{route['source']}</code> → "
            f"<code>{route['target']}</code>\n"
        )

    return text


@dp.message(CommandStart())
async def start_handler(message: Message):
    if not is_owner(message.from_user.id):
        return

    await message.answer(
        "<b>Управление пересылками</b>\n\nВыбери действие:",
        reply_markup=main_keyboard(),
    )


@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        " <b>Управление пересылками</b>\n\nВыбери действие:",
        reply_markup=main_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "add_route")
async def add_route_handler(callback: CallbackQuery, state: FSMContext):
    if not is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await state.set_state(AddRoute.source)

    await callback.message.edit_text(
        " <b>Добавление пересылки</b>\n\n"
        "Отправь <b>ID канала-источника</b>.\n\n"
        "Например: <code>-1004328683164</code>",
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@dp.message(AddRoute.source)
async def source_handler(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    try:
        source = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(
            "❌ ID должен быть числом.\n"
            "Например: <code>-1004328683164</code>"
        )
        return

    await state.update_data(source=source)
    await state.set_state(AddRoute.target)

    await message.answer(
        "Теперь отправь <b>ID чата-получателя</b>.\n\n"
        "Например: <code>-1003970374690</code>",
        reply_markup=back_keyboard(),
    )


@dp.message(AddRoute.target)
async def target_handler(message: Message, state: FSMContext):
    if not is_owner(message.from_user.id):
        return

    try:
        target = int(message.text.strip())
    except (ValueError, AttributeError):
        await message.answer(
            "❌ ID должен быть числом.\n"
            "Например: <code>-1003970374690</code>"
        )
        return

    data = await state.get_data()
    source = data["source"]

    if any(
        route["source"] == source and route["target"] == target
        for route in routes
    ):
        await state.clear()
        await message.answer(
            " Такая пересылка уже существует.",
            reply_markup=main_keyboard(),
        )
        return

    routes.append({
        "source": source,
        "target": target,
    })

    save_routes()
    await state.clear()

    await message.answer(
        "✅ <b>Пересылка добавлена!</b>\n\n"
        f"Канал: <code>{source}</code>\n"
        f"Чат: <code>{target}</code>",
        reply_markup=main_keyboard(),
    )

    logging.info("Добавлен маршрут: %s -> %s", source, target)


@dp.callback_query(F.data == "list_routes")
async def list_routes_handler(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    await callback.message.edit_text(
        routes_text(),
        reply_markup=back_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "delete_route")
async def delete_route_handler(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    if not routes:
        await callback.message.edit_text(
            "🗑 <b>Активных пересылок нет.</b>",
            reply_markup=back_keyboard(),
        )
    else:
        await callback.message.edit_text(
            "🗑 <b>Выбери пересылку для удаления:</b>",
            reply_markup=delete_keyboard(),
        )

    await callback.answer()


@dp.callback_query(F.data.startswith("delete:"))
async def delete_selected_handler(callback: CallbackQuery):
    if not is_owner(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    try:
        index = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Ошибка.", show_alert=True)
        return

    if index < 0 or index >= len(routes):
        await callback.answer("Пересылка уже удалена.", show_alert=True)
        return

    removed = routes.pop(index)
    save_routes()

    await callback.message.edit_text(
        "<b>Пересылка удалена.</b>\n\n"
        f"<code>{removed['source']}</code> → "
        f"<code>{removed['target']}</code>",
        reply_markup=main_keyboard(),
    )
    await callback.answer()


@dp.channel_post()
async def channel_post_handler(message: Message):
    for route in routes:
        if route["source"] != message.chat.id:
            continue

        try:
            await bot.forward_message(
                chat_id=route["target"],
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

            logging.info(
                "Forwarded %s -> %s, message %s",
                message.chat.id,
                route["target"],
                message.message_id,
            )

        except Exception:
            logging.exception(
                "Failed forwarding %s -> %s",
                message.chat.id,
                route["target"],
            )


async def main():
    logging.info("Бот запущен. Активных маршрутов: %s", len(routes))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
