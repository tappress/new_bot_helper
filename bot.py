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

from settings import settings

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Налаштування бота
API_TOKEN = settings.TELEGRAM_BOT_TOKEN
API_BASE_URL = "http://localhost:8000"

# Створення об'єктів бота і диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()


# Визначення станів FSM для обробки запитів
class WeatherState(StatesGroup):
    waiting_for_city = State()


class CurrencyState(StatesGroup):
    waiting_for_currencies = State()


class NewsState(StatesGroup):
    waiting_for_query = State()


# Функція для витягування тексту з повідомлення
def extract_text_from_message(message: Message) -> str:
    """Витягує текст з повідомлення, якщо він є"""
    if message.text:
        return message.text
    elif message.caption:
        return message.caption
    return ""


# Функції для простого аналізу текстових запитів на основі ключових слів
def has_weather_keywords(text: str) -> bool:
    """Перевіряє, чи містить текст ключові слова, пов'язані з погодою"""
    keywords = [
        "погода",
        "температура",
        "градус",
        "дощ",
        "сніг",
        "хмарно",
        "ясно",
        "вітер",
    ]
    return any(keyword in text.lower() for keyword in keywords)


def has_currency_keywords(text: str) -> bool:
    """Перевіряє, чи містить текст ключові слова, пов'язані з валютою"""
    keywords = [
        "курс",
        "валюта",
        "долар",
        "євро",
        "гривня",
        "грн",
        "usd",
        "eur",
        "uah",
        "обмін",
    ]
    return any(keyword in text.lower() for keyword in keywords)


def has_news_keywords(text: str) -> bool:
    """Перевіряє, чи містить текст ключові слова, пов'язані з новинами"""
    keywords = ["новини", "новина", "події", "що відбувається", "що нового", "статті"]
    return any(keyword in text.lower() for keyword in keywords)


def extract_city_from_text(text: str) -> str:
    """Спрощений алгоритм для витягування назви міста з тексту"""
    common_cities = [
        "київ",
        "харків",
        "одеса",
        "дніпро",
        "львів",
        "запоріжжя",
        "донецьк",
        "луганськ",
        "симферополь",
        "херсон",
        "миколаїв",
        "вінниця",
        "полтава",
        "чернігів",
        "черкаси",
        "хмельницький",
        "житомир",
        "суми",
        "рівне",
        "івано-франківськ",
        "тернопіль",
        "луцьк",
        "ужгород",
        "чернівці",
    ]

    # Перевіряємо, чи є в тексті назва відомого міста
    text_lower = text.lower()
    for city in common_cities:
        if city in text_lower:
            # Повертаємо місто з правильним регістром (перша літера велика)
            return city.capitalize()

    # Якщо відоме місто не знайдено, повертаємо Київ за замовчуванням
    return "Київ"


def extract_currency_from_text(text: str) -> tuple:
    """Спрощений алгоритм для витягування валютної пари з тексту"""
    text_lower = text.lower()

    base = "USD"  # За замовчуванням
    target = "UAH"  # За замовчуванням

    # Визначаємо базову валюту
    if "євро" in text_lower or "eur" in text_lower:
        base = "EUR"
    elif "долар" in text_lower or "usd" in text_lower:
        base = "USD"
    elif "фунт" in text_lower or "gbp" in text_lower:
        base = "GBP"

    # Визначаємо цільову валюту
    if "гривня" in text_lower or "грн" in text_lower or "uah" in text_lower:
        target = "UAH"
    elif "💩" in text_lower or "rub" in text_lower:
        target = "RUB"
    elif "злотий" in text_lower or "pln" in text_lower:
        target = "PLN"

    return base, target


# Утиліта для роботи з API
async def make_api_request(
    endpoint: str,
    params: Dict[str, Any],
    message: Message,
    error_message: str,
    formatter: Callable[[Dict[str, Any]], str],
    state: Optional[FSMContext] = None,
) -> bool:
    """
    Універсальна функція для виконання API-запитів з обробкою помилок і форматуванням відповіді.

    Args:
        endpoint: Кінцева точка API
        params: Параметри запиту
        message: Об'єкт повідомлення для відповіді
        error_message: Повідомлення про помилку
        formatter: Функція для форматування успішної відповіді
        state: Об'єкт стану FSM для очищення після запиту (опціонально)

    Returns:
        bool: True якщо запит успішний, False в іншому випадку
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/{endpoint}", params=params)
            response.raise_for_status()
            data = response.json()

            # Форматуємо і відправляємо відповідь
            formatted_response = formatter(data)
            await message.answer(formatted_response)

            # Очищаємо стан, якщо він був переданий
            if state:
                await state.clear()

            return True

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Для 404 зазвичай є спеціальне повідомлення на основі параметрів
            param_value = next(iter(params.values()), "")
            await message.answer(
                f"Запит на '{param_value}' не знайдено. Спробуйте інший запит."
            )
        else:
            await message.answer(f"{error_message} Спробуйте пізніше.")
        logger.error(f"Помилка HTTP при запиті до {endpoint}: {str(e)}")
    except Exception as e:
        await message.answer(f"{error_message} Спробуйте пізніше.")
        logger.error(f"Непередбачена помилка при запиті до {endpoint}: {str(e)}")

    # Очищаємо стан у випадку помилки, якщо він був переданий
    if state:
        await state.clear()

    return False


# Функції для форматування відповідей від API
def format_weather_response(data: Dict[str, Any]) -> str:
    """Форматує дані про погоду у текстове повідомлення"""
    return (
        f"🌡 Погода в {data['city']}, {data['country']}:\n\n"
        f"🌡 Температура: {data['temperature']}°C (відчувається як {data['feels_like']}°C)\n"
        f"📝 Стан: {data['description']}\n"
        f"💧 Вологість: {data['humidity']}%\n"
        f"🌬 Швидкість вітру: {data['wind_speed']} м/с\n"
        f"🕒 Дані оновлено: {data['timestamp']}"
    )


def format_currency_response(data: Dict[str, Any]) -> str:
    """Форматує дані про курс валют у текстове повідомлення"""
    base = data.get("base", "")
    target = data.get("target", "")
    rate = data.get("rate", 0)

    return (
        f"💱 Курс валют {base} → {target}:\n\n"
        f"1 {base} = {rate:.4f} {target}\n"
        f"10 {base} = {(rate * 10):.4f} {target}\n"
        f"100 {base} = {(rate * 100):.4f} {target}\n"
        f"1000 {base} = {(rate * 1000):.4f} {target}\n\n"
        f"🕒 Дані на: {data['date']}"
    )


def format_news_response(
    data: Dict[str, Any], query: Optional[str] = None, category: Optional[str] = None
) -> str:
    """Форматує дані про новини у текстове повідомлення"""
    articles = data.get("articles", [])

    if not articles:
        return "На жаль, новин за вашим запитом не знайдено."

    if query:
        header = f"📰 Новини за запитом '{query}':\n\n"
    elif category:
        header = f"📰 Останні новини в категорії '{category}':\n\n"
    else:
        header = "📰 Останні новини:\n\n"

    news_message = header

    for i, article in enumerate(articles[:5], 1):
        news_message += (
            f"{i}. {article['title']}\n"
            f"Джерело: {article['source']}\n"
            f"Посилання: {article['url']}\n\n"
        )

    return news_message


# Процесори запитів
async def process_weather_request(
    message: Message, city: str, state: Optional[FSMContext] = None
):
    """Обробка запиту на погоду"""
    await make_api_request(
        endpoint="weather",
        params={"city": city},
        message=message,
        error_message="Помилка при отриманні даних про погоду.",
        formatter=format_weather_response,
        state=state,
    )


async def process_currency_request(
    message: Message, base: str, target: str, state: Optional[FSMContext] = None
):
    """Обробка запиту на курс валют"""
    await make_api_request(
        endpoint="currency",
        params={"base": base, "target": target},
        message=message,
        error_message="Помилка при отриманні курсу валют.",
        formatter=format_currency_response,
        state=state,
    )


async def process_news_request(
    message: Message,
    query: Optional[str] = None,
    category: Optional[str] = None,
    state: Optional[FSMContext] = None,
):
    """Обробка запиту на новини"""
    params = {"country": "ua"}
    if query:
        params["query"] = query
    if category:
        params["category"] = category

    def news_formatter(data: Dict[str, Any]) -> str:
        return format_news_response(data, query, category)

    await make_api_request(
        endpoint="news",
        params=params,
        message=message,
        error_message="Помилка при отриманні новин.",
        formatter=news_formatter,
        state=state,
    )


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


# Обробка вільного тексту (ключові слова)
@router.message(F.text)
async def handle_text(message: Message):
    """Обробка звичайних текстових повідомлень на основі ключових слів"""
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


# Реєстрація роутера і запуск бота
dp.include_router(router)


async def main():
    logging.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
