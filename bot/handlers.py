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
from bot.speech_processor import speech_processor
from bot.utils import (
    process_weather_request,
    process_currency_request,
    process_news_request,
    extract_text_from_message,
    has_weather_keywords,
    extract_city_from_text,
    has_currency_keywords,
    extract_currency_from_text,
    has_news_keywords
)
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
        f"Ви також можете просто написати свій запит звичайним текстом або надіслати голосове повідомлення, "
        f"наприклад: 'Яка погода у Львові?' або 'Який курс долара?'"
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


# Обробка голосових повідомлень
@router.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext):
    """Обробка голосових повідомлень"""
    # Надсилаємо статус "друкує" під час обробки
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Повідомлення про початок обробки
    processing_message = await message.answer("🎤 Розпізнаю голосове повідомлення...")

    try:
        # Розпізнаємо мовлення
        recognized_text = await speech_processor.recognize_speech(message)

        if not recognized_text:
            await message.answer(
                "⚠️ Не вдалося розпізнати мовлення. Будь ласка, спробуйте ще раз або надішліть текстове повідомлення."
            )
            return

        # Логуємо розпізнаний текст і повідомляємо користувача
        logger.info(f"Розпізнано текст з голосового повідомлення: {recognized_text}")
        await message.answer(f"🎯 Розпізнано: \"{recognized_text}\"")

        # Видаляємо повідомлення про обробку
        await processing_message.delete()

        # Обробляємо розпізнаний текст через NLP з голосовою відповіддю
        nlp_processed = await process_nlp_request(message, state, recognized_text, use_voice_reply=True)

        # Якщо NLP не зміг обробити, використовуємо простіший метод ключових слів
        if not nlp_processed:
            logger.info("NLP не зміг обробити голосовий запит, використовуємо метод ключових слів")

            # Визначаємо тип запиту за ключовими словами
            if has_weather_keywords(recognized_text):
                city = extract_city_from_text(recognized_text)
                response_text = await process_weather_request(message, city, state, return_text=True, voice_reply=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            elif has_currency_keywords(recognized_text):
                base, target = extract_currency_from_text(recognized_text)
                response_text = await process_currency_request(message, base, target, state, return_text=True,
                                                               voice_reply=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            elif has_news_keywords(recognized_text):
                response_text = await process_news_request(message, state=state, return_text=True, voice_reply=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            else:
                response_text = (
                    "Не вдалося розпізнати ваш запит. Спробуйте використати команди:\n"
                    "/weather - Погода\n"
                    "/currency - Курс валют\n"
                    "/news - Новини"
                )
                await message.answer(response_text)

    except Exception as e:
        logger.error(f"Помилка при обробці голосового повідомлення: {e}")
        await message.answer("⚠️ Сталася помилка при обробці голосового повідомлення.")

        # Видаляємо повідомлення про обробку, якщо воно ще існує
        try:
            await processing_message.delete()
        except Exception:
            pass


# Додамо команду для перевірки можливості голосової відповіді
@router.message(Command("voice"))
async def cmd_voice_test(message: Message):
    """Тестова команда для перевірки голосової відповіді"""
    await message.answer("Перевіряю можливість голосової відповіді...")
    test_text = "Привіт! Я можу говорити. Ви можете надсилати мені голосові повідомлення, і я відповідатиму голосом."

    success = await speech_processor.send_voice_reply(message, test_text)

    if not success:
        await message.answer("⚠️ На жаль, виникла проблема з генерацією голосової відповіді.")


# Додаємо команду з інструкцією по використанню голосових можливостей
@router.message(Command("help_voice"))
async def cmd_help_voice(message: Message):
    """Інструкція з використання голосових можливостей"""
    help_text = (
        "🎤 *Голосові можливості бота*\n\n"
        "Бот підтримує голосові запити та відповіді:\n\n"
        "1. *Голосові запити* - ви можете надіслати голосове повідомлення з запитом, наприклад:\n"
        "   - \"Яка погода у Києві?\"\n"
        "   - \"Який курс долара?\"\n"
        "   - \"Розкажи останні новини\"\n\n"
        "2. *Голосові відповіді* - бот може відповідати вам голосом.\n\n"
        "Для перевірки голосової функціональності використовуйте команду /voice\n\n"
        "Бот може не розпізнати деякі слова через фоновий шум, акцент або якість мікрофона. "
        "У таких випадках спробуйте говорити повільніше та чіткіше, або використайте текстовий запит."
    )

    await message.answer(help_text, parse_mode="Markdown")


# Обробка звичайних текстових повідомлень
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

