import asyncio
import logging
from typing import Callable, Any, Dict, Optional, Tuple

import httpx
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.nlp_processor import process_nlp_request
from bot.utils import process_weather_request, process_currency_request, process_news_request, \
    extract_text_from_message, has_weather_keywords, extract_city_from_text, has_currency_keywords, \
    extract_currency_from_text, has_news_keywords
from settings import settings

logger = logging.getLogger(__name__)

router = Router()


# Визначення станів FSM для обробки запитів
class WeatherState(StatesGroup):
    waiting_for_city = State()


class CurrencyState(StatesGroup):
    waiting_for_currencies = State()


class NewsState(StatesGroup):
    waiting_for_query = State()


# Хендлери для обробки команд
@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обробка команди /start"""
    start_message = (
        f"👋 Привіт, {message.from_user.first_name}!\n\n"
        f"Я інформаційний бот, який може надати вам інформацію про погоду, курс валют та останні новини.\n\n"
        f"Доступні команди:\n"
        f"- /weather - Дізнатися погоду в місті\n"
        f"- /currency - Отримати курс валют\n"
        f"- /news - Прочитати останні новини\n\n"
        f"Ви також можете просто написати свій запит звичайним текстом, наприклад: 'Яка погода у Львові?' або 'Який курс долара?'"
    )

    await message.answer(start_message)


@router.message(Command("weather"))
async def cmd_weather(message: Message, state: FSMContext):
    """Обробка команди /weather"""
    await message.answer("Введіть назву міста для перевірки погоди:")
    await state.set_state(WeatherState.waiting_for_city)


@router.message(WeatherState.waiting_for_city)
async def process_weather_city(message: Message, state: FSMContext):
    """Обробка введеного користувачем міста для погоди"""
    city = message.text.strip()
    await process_weather_request(message, city, state)


@router.message(Command("currency"))
async def cmd_currency(message: Message):
    """Обробка команди /currency"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="USD → UAH", callback_data="currency_USD_UAH"
                ),
                InlineKeyboardButton(
                    text="EUR → UAH", callback_data="currency_EUR_UAH"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="UAH → USD", callback_data="currency_UAH_USD"
                ),
                InlineKeyboardButton(
                    text="UAH → EUR", callback_data="currency_UAH_EUR"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="EUR → USD", callback_data="currency_EUR_USD"
                ),
                InlineKeyboardButton(
                    text="USD → EUR", callback_data="currency_USD_EUR"
                ),
            ],
        ]
    )

    await message.answer(
        "Виберіть валютну пару або введіть свою пару через пробіл (наприклад, 'USD UAH'):",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("currency_"))
async def process_currency_callback(callback: CallbackQuery):
    """Обробка вибору валютної пари через кнопки"""
    await callback.answer()

    # Розбираємо дані з callback
    _, base, target = callback.data.split("_")
    await process_currency_request(callback.message, base, target)


@router.message(Command("news"))
async def cmd_news(message: Message):
    """Обробка команди /news"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Загальні", callback_data="news_general"),
                InlineKeyboardButton(text="Бізнес", callback_data="news_business"),
            ],
            [
                InlineKeyboardButton(
                    text="Технології", callback_data="news_technology"
                ),
                InlineKeyboardButton(text="Спорт", callback_data="news_sports"),
            ],
            [
                InlineKeyboardButton(text="Наука", callback_data="news_science"),
                InlineKeyboardButton(text="Здоров'я", callback_data="news_health"),
            ],
            [InlineKeyboardButton(text="За запитом", callback_data="news_custom")],
        ]
    )

    await message.answer(
        "Виберіть категорію новин або введіть свій запит:", reply_markup=keyboard
    )


@router.callback_query(F.data.startswith("news_"))
async def process_news_callback(callback: CallbackQuery, state: FSMContext):
    """Обробка вибору категорії новин через кнопки"""
    await callback.answer()

    category = callback.data.split("_")[1]

    if category == "custom":
        await callback.message.answer("Введіть свій запит для пошуку новин:")
        await state.set_state(NewsState.waiting_for_query)
        return

    await process_news_request(callback.message, category=category)


@router.message(NewsState.waiting_for_query)
async def process_news_query(message: Message, state: FSMContext):
    """Обробка введеного користувачем запиту для новин"""
    query = message.text.strip()
    await process_news_request(message, query=query, state=state)


# Обробка вільного тексту з використанням NLP
@router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    """Обробка звичайних текстових повідомлень з використанням NLP"""

    # Спробуємо обробити запит за допомогою NLP
    nlp_processed = await process_nlp_request(message, state)

    # Якщо NLP не зміг обробити запит, використовуємо базовий метод ключових слів
    if not nlp_processed:
        logger.info("NLP не зміг обробити запит, використовуємо метод ключових слів")
        text = extract_text_from_message(message)

        if not text:
            return

        # Визначаємо тип запиту за ключовими словами
        if has_weather_keywords(text):
            city = extract_city_from_text(text)
            await process_weather_request(message, city)

        elif has_currency_keywords(text):
            base, target = extract_currency_from_text(text)
            await process_currency_request(message, base, target)

        elif has_news_keywords(text):
            await process_news_request(message)

        else:
            await message.answer(
                "Не вдалося розпізнати ваш запит. Спробуйте використати команди:\n"
                "/weather - Погода\n"
                "/currency - Курс валют\n"
                "/news - Новини"
            )
