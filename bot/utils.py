import logging
import re
from typing import Tuple, Optional

import httpx
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from settings import settings

logger = logging.getLogger(__name__)


async def process_weather_request(
        message: Message, city: str = "Київ", state: Optional[FSMContext] = None
):
    """
    Обробка запиту погоди
    :param message: Повідомлення від користувача
    :param city: Місто для перевірки погоди
    :param state: FSM контекст (опціонально)
    """
    if state:
        await state.clear()

    # Повідомлення про обробку
    processing_message = await message.answer(f"🔍 Шукаю інформацію про погоду в місті {city}...")

    try:
        # Запит до API погоди
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/weather", params={"city": city}
            )

            if response.status_code == 200:
                data = response.json()

                # Формування повідомлення з результатами
                weather_message = (
                    f"🌡️ Погода в {data['city']}, {data['country']}:\n\n"
                    f"Температура: {data['temperature']}°C (відчувається як {data['feels_like']}°C)\n"
                    f"Опис: {data['description']}\n"
                    f"Вологість: {data['humidity']}%\n"
                    f"Тиск: {data['pressure']} гПа\n"
                    f"Швидкість вітру: {data['wind_speed']} м/с"
                )

                await message.answer(weather_message)
            else:
                error_data = response.json()
                await message.answer(f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати дані про погоду')}")
    except Exception as e:
        logger.error(f"Помилка при запиті погоди: {e}")
        await message.answer("⚠️ Сталася помилка при запиті погоди. Спробуйте ще раз пізніше.")
    finally:
        # Видаляємо повідомлення про обробку
        try:
            await processing_message.delete()
        except Exception as e:
            logger.error(f"Помилка при видаленні повідомлення: {e}")


async def process_currency_request(
        message: Message, base: str = "USD", target: str = "UAH", state: Optional[FSMContext] = None
):
    """
    Обробка запиту курсу валют
    :param message: Повідомлення від користувача
    :param base: Базова валюта
    :param target: Цільова валюта
    :param state: FSM контекст (опціонально)
    """
    if state:
        await state.clear()

    # Нормалізація кодів валют
    base = base.upper()
    target = target.upper()

    # Повідомлення про обробку
    processing_message = await message.answer(f"🔍 Шукаю інформацію про курс {base} до {target}...")

    try:
        # Запит до API курсу валют
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/currency",
                params={"base": base, "target": target},
            )

            if response.status_code == 200:
                data = response.json()

                # Формування повідомлення з результатами
                currency_message = (
                    f"💱 Курс валют {data['base']} ➡️ {data['target']}:\n\n"
                    f"1 {data['base']} = {data['rate']:.4f} {data['target']}\n"
                    f"Дата оновлення: {data['date']}"
                )

                await message.answer(currency_message)
            else:
                error_data = response.json()
                await message.answer(
                    f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати дані про курс валют')}")
    except Exception as e:
        logger.error(f"Помилка при запиті курсу валют: {e}")
        await message.answer("⚠️ Сталася помилка при запиті курсу валют. Спробуйте ще раз пізніше.")
    finally:
        # Видаляємо повідомлення про обробку
        try:
            await processing_message.delete()
        except Exception as e:
            logger.error(f"Помилка при видаленні повідомлення: {e}")


async def process_news_request(
        message: Message,
        query: Optional[str] = None,
        category: str = "general",
        state: Optional[FSMContext] = None
):
    """
    Обробка запиту новин
    :param message: Повідомлення від користувача
    :param query: Запит для пошуку новин (опціонально)
    :param category: Категорія новин
    :param state: FSM контекст (опціонально)
    """
    if state:
        await state.clear()

    # Повідомлення про обробку
    processing_text = f"🔍 Шукаю новини"
    if query:
        processing_text += f" за запитом '{query}'"
    if category != "general":
        processing_text += f" в категорії '{category}'"
    processing_message = await message.answer(processing_text + "...")

    try:
        # Запит до API новин
        params = {"category": category}
        if query:
            params["query"] = query

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/news", params=params
            )

            if response.status_code == 200:
                data = response.json()

                if data["total_results"] > 0:
                    # Заголовок повідомлення
                    news_title = "📰 Останні новини"
                    if query:
                        news_title += f" за запитом '{query}'"
                    if category != "general":
                        news_title += f" в категорії '{category}'"

                    # Формування списку новин
                    news_list = ""
                    for i, article in enumerate(data["articles"], 1):
                        if i > 5:  # Обмеження на 5 новин
                            break

                        news_list += f"{i}. <a href='{article['url']}'>{article['title']}</a>\n"
                        if article.get("description"):
                            news_list += f"   {article['description'][:100]}...\n"
                        if article.get("source"):
                            news_list += f"   Джерело: {article['source']}\n"
                        news_list += "\n"

                    # Відправка повідомлення з новинами
                    await message.answer(
                        f"{news_title}\n\n{news_list}",
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                else:
                    await message.answer("📭 Новин за вашим запитом не знайдено.")
            else:
                error_data = response.json()
                await message.answer(f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати новини')}")
    except Exception as e:
        logger.error(f"Помилка при запиті новин: {e}")
        await message.answer("⚠️ Сталася помилка при запиті новин. Спробуйте ще раз пізніше.")
    finally:
        # Видаляємо повідомлення про обробку
        try:
            await processing_message.delete()
        except Exception as e:
            logger.error(f"Помилка при видаленні повідомлення: {e}")


def extract_text_from_message(message: Message) -> str:
    """
    Отримання тексту з повідомлення
    :param message: Повідомлення
    :return: Текст повідомлення
    """
    if message.text:
        return message.text.strip()
    elif message.caption:
        return message.caption.strip()
    return ""


def has_weather_keywords(text: str) -> bool:
    """
    Перевірка наявності ключових слів погоди
    :param text: Текст для перевірки
    :return: True, якщо знайдено ключові слова
    """
    keywords = ["погода", "температура", "градус", "тепло", "холодно", "дощ"]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


def extract_city_from_text(text: str) -> str:
    """
    Витягування назви міста з тексту
    :param text: Текст для аналізу
    :return: Назва міста або "Київ" за замовчуванням
    """
    # Паттерн для пошуку міста після слів "в", "у", "для", "на"
    pattern = r"(?:в|у|для|на)\s+([А-ЯІЇЄҐA-Z][а-яіїєґa-z]+)"
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1)

    # Якщо не знайдено за паттерном, шукаємо слово з великої літери
    words = text.split()
    for word in words:
        if word[0].isupper() and len(word) > 2 and word.lower() not in ["яка", "який", "яке", "які", "скажи",
                                                                        "скажіть"]:
            return word

    # За замовчуванням
    return "Київ"


def has_currency_keywords(text: str) -> bool:
    """
    Перевірка наявності ключових слів валют
    :param text: Текст для перевірки
    :return: True, якщо знайдено ключові слова
    """
    keywords = ["курс", "валюта", "долар", "євро", "гривня", "usd", "eur", "uah"]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)


def extract_currency_from_text(text: str) -> Tuple[str, str]:
    """
    Витягування кодів валют з тексту
    :param text: Текст для аналізу
    :return: Кортеж (базова валюта, цільова валюта)
    """
    # Словник для розпізнавання валют за назвою
    currency_map = {
        "долар": "USD",
        "доларах": "USD",
        "доларів": "USD",
        "долара": "USD",
        "євро": "EUR",
        "гривня": "UAH",
        "гривні": "UAH",
        "гривень": "UAH",
        "гривнях": "UAH",
        "usd": "USD",
        "eur": "EUR",
        "uah": "UAH"
    }

    text_lower = text.lower()

    # Шукаємо відомі коди валют
    found_currencies = []
    for currency_name, currency_code in currency_map.items():
        if currency_name in text_lower and currency_code not in found_currencies:
            found_currencies.append(currency_code)

    # Якщо знайдено дві валюти, повертаємо їх
    if len(found_currencies) >= 2:
        return found_currencies[0], found_currencies[1]

    # Якщо знайдено одну валюту, комбінуємо її з UAH
    if len(found_currencies) == 1:
        if found_currencies[0] == "UAH":
            return "USD", "UAH"
        return found_currencies[0], "UAH"

    # За замовчуванням
    return "USD", "UAH"


def has_news_keywords(text: str) -> bool:
    """
    Перевірка наявності ключових слів новин
    :param text: Текст для перевірки
    :return: True, якщо знайдено ключові слова
    """
    keywords = ["новини", "новина", "події", "що відбувається", "статті"]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in keywords)
