import logging
import re
from typing import Tuple, Optional

import httpx
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from settings import settings

logger = logging.getLogger(__name__)


async def process_weather_request(
        message: Message, city: str = "Київ", state: Optional[FSMContext] = None,
        return_text: bool = False, voice_reply: bool = False
) -> Optional[str]:
    """
    Обробка запиту погоди
    :param message: Повідомлення від користувача
    :param city: Місто для перевірки погоди
    :param state: FSM контекст (опціонально)
    :param return_text: Повернути текст замість надсилання повідомлення
    :param voice_reply: Чи потрібна голосова відповідь
    :return: Текст відповіді, якщо return_text=True
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

                # Спрощений варіант для голосової відповіді
                if voice_reply:
                    weather_voice_message = (
                        f"Погода в місті {data['city']}. "
                        f"Температура {data['temperature']} градусів, відчувається як {data['feels_like']}. "
                        f"{data['description']}. "
                        f"Вологість {data['humidity']} відсотків. "
                        f"Швидкість вітру {data['wind_speed']} метрів на секунду."
                    )

                    if return_text:
                        return weather_voice_message

                if return_text:
                    return weather_message

                await message.answer(weather_message)
                return None
            else:
                error_data = response.json()
                error_message = f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати дані про погоду')}"

                if return_text:
                    return error_message

                await message.answer(error_message)
                return None
    except Exception as e:
        logger.error(f"Помилка при запиті погоди: {e}")
        error_message = "⚠️ Сталася помилка при запиті погоди. Спробуйте ще раз пізніше."

        if return_text:
            return error_message

        await message.answer(error_message)
        return None
    finally:
        # Видаляємо повідомлення про обробку
        try:
            await processing_message.delete()
        except Exception as e:
            logger.error(f"Помилка при видаленні повідомлення: {e}")


async def process_currency_request(
        message: Message, base: str = "USD", target: str = "UAH", state: Optional[FSMContext] = None,
        return_text: bool = False, voice_reply: bool = False
) -> Optional[str]:
    """
    Обробка запиту курсу валют
    :param message: Повідомлення від користувача
    :param base: Базова валюта
    :param target: Цільова валюта
    :param state: FSM контекст (опціонально)
    :param return_text: Повернути текст замість надсилання повідомлення
    :param voice_reply: Чи потрібна голосова відповідь
    :return: Текст відповіді, якщо return_text=True
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

                # Спрощений варіант для голосової відповіді
                if voice_reply:
                    currency_voice_message = (
                        f"Курс {data['base']} до {data['target']} становить {data['rate']:.2f}. "
                        f"Один {pronunciation_of_currency(data['base'])} "
                        f"коштує {data['rate']:.2f} {pronunciation_of_currency(data['target'], data['rate'])}."
                    )

                    if return_text:
                        return currency_voice_message

                if return_text:
                    return currency_message

                await message.answer(currency_message)
                return None
            else:
                error_data = response.json()
                error_message = f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати дані про курс валют')}"

                if return_text:
                    return error_message

                await message.answer(error_message)
                return None
    except Exception as e:
        logger.error(f"Помилка при запиті курсу валют: {e}")
        error_message = "⚠️ Сталася помилка при запиті курсу валют. Спробуйте ще раз пізніше."

        if return_text:
            return error_message

        await message.answer(error_message)
        return None
    finally:
        # Видаляємо повідомлення про обробку
        try:
            await processing_message.delete()
        except Exception as e:
            logger.error(f"Помилка при видаленні повідомлення: {e}")


def pronunciation_of_currency(currency_code: str, amount: float = 1.0) -> str:
    """
    Правильна вимова назви валюти залежно від кількості
    :param currency_code: Код валюти
    :param amount: Кількість
    :return: Правильна форма назви валюти
    """
    if currency_code == "USD":
        if amount == 1:
            return "долар"
        elif 1 < amount < 5:
            return "долари"
        else:
            return "доларів"
    elif currency_code == "EUR":
        if amount == 1:
            return "євро"
        else:
            return "євро"
    elif currency_code == "UAH":
        if amount == 1:
            return "гривня"
        elif 1 < amount < 5:
            return "гривні"
        else:
            return "гривень"
    return currency_code


async def process_news_request(
        message: Message,
        query: Optional[str] = None,
        category: str = "general",
        country: str = "ua",
        state: Optional[FSMContext] = None,
        return_text: bool = False,
        voice_reply: bool = False
) -> Optional[str]:
    """
    Обробка запиту новин
    :param message: Повідомлення від користувача
    :param query: Запит для пошуку новин (опціонально)
    :param category: Категорія новин
    :param country: Країна новин (за замовчуванням "ua")
    :param state: FSM контекст (опціонально)
    :param return_text: Повернути текст замість надсилання повідомлення
    :param voice_reply: Чи потрібна голосова відповідь
    :return: Текст відповіді, якщо return_text=True
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
        params = {"category": category, "country": country}
        if query:
            params["query"] = query

        # Для спортивних новин спробуємо спочатку без обмеження мови
        if category == "sports" and country == "ua":
            # Створюємо копію параметрів без ключа query
            sports_params = params.copy()
            if "query" in sports_params:
                del sports_params["query"]

            logger.info(f"Спеціальна обробка для спортивних новин: {sports_params}")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.API_BASE_URL}/news", params=params
            )

            if response.status_code == 200:
                data = response.json()

                # Якщо не знайдено для спортивних новин, спробуємо без query
                if data["total_results"] == 0 and category == "sports" and query:
                    logger.info("Спортивні новини не знайдено з query, пробуємо без query")
                    params_without_query = params.copy()
                    del params_without_query["query"]

                    response = await client.get(
                        f"{settings.API_BASE_URL}/news", params=params_without_query
                    )
                    if response.status_code == 200:
                        data = response.json()

                # Якщо все ще немає результатів для спортивних новин, спробуємо з US
                if data["total_results"] == 0 and category == "sports":
                    logger.info("Спортивні новини не знайдено для UA, пробуємо US")
                    us_params = {"category": "sports", "country": "us"}

                    response = await client.get(
                        f"{settings.API_BASE_URL}/news", params=us_params
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
                    voice_news_list = ""

                    for i, article in enumerate(data["articles"], 1):
                        if i > 5:  # Обмеження на 5 новин
                            break

                        news_list += f"{i}. <a href='{article['url']}'>{article['title']}</a>\n"

                        # Додаємо до тексту для голосової відповіді
                        voice_news_list += f"Новина {i}. {article['title']}. "

                        if article.get("description"):
                            news_list += f"   {article['description'][:100]}...\n"
                            voice_news_list += f"{article['description'][:100]}. "

                        if article.get("source"):
                            news_list += f"   Джерело: {article['source']}\n"
                            voice_news_list += f"Джерело: {article['source']}. "

                        news_list += "\n"
                        voice_news_list += "\n"

                    # Повний текст повідомлення
                    news_message = f"{news_title}\n\n{news_list}"

                    # Текст для голосової відповіді
                    if voice_reply:
                        news_voice_message = f"{news_title}. {voice_news_list}"

                        if return_text:
                            return news_voice_message

                    if return_text:
                        return news_message

                    # Відправка повідомлення з новинами
                    await message.answer(
                        news_message,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    return None
                else:
                    no_news_message = "📭 Новин за вашим запитом не знайдено."

                    if return_text:
                        return no_news_message

                    await message.answer(no_news_message)
                    return None
            else:
                error_data = response.json()
                error_message = f"⚠️ Помилка: {error_data.get('detail', 'Не вдалося отримати новини')}"

                if return_text:
                    return error_message

                await message.answer(error_message)
                return None
    except Exception as e:
        logger.error(f"Помилка при запиті новин: {e}")
        error_message = "⚠️ Сталася помилка при запиті новин. Спробуйте ще раз пізніше."

        if return_text:
            return error_message

        await message.answer(error_message)
        return None
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
    # Словник для перетворення міст у відмінках до називного відмінку
    city_cases = {
        "києві": "Київ",
        "львові": "Львів",
        "одесі": "Одеса",
        "харкові": "Харків",
        "дніпрі": "Дніпро",
        "житомирі": "Житомир",
        "вінниці": "Вінниця",
        "полтаві": "Полтава",
        "чернігові": "Чернігів",
        "херсоні": "Херсон",
        "запоріжжі": "Запоріжжя"
    }

    # Спочатку перевіряємо, чи не згадані міста у відмінках
    text_lower = text.lower()
    for city_case, city_name in city_cases.items():
        if city_case in text_lower:
            logger.info(f"Знайдено місто у відмінку: {city_case} -> {city_name}")
            return city_name

    # Паттерн для пошуку міста після слів "в", "у", "для", "на"
    pattern = r"(?:в|у|для|на)\s+([А-ЯІЇЄҐA-Z][а-яіїєґa-z]+)"
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        city = match.group(1)
        # Перевіряємо, чи місто у відмінку
        if city.lower() in city_cases:
            return city_cases[city.lower()]
        return city

    # Якщо не знайдено за паттерном, шукаємо слово з великої літери
    words = text.split()
    for word in words:
        if len(word) > 2 and word[0].isupper() and word.lower() not in ["яка", "який", "яке", "які", "скажи",
                                                                        "скажіть"]:
            # Перевіряємо, чи місто у відмінку
            if word.lower() in city_cases:
                return city_cases[word.lower()]
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