import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from settings import settings

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Створення FastAPI додатку
app = FastAPI(title="Інформаційний API", description="API для отримання погоди, курсу валют та новин")

# API ключі
WEATHER_API_KEY = settings.WEATHER_API_KEY  # OpenWeatherMap API ключ
NEWS_API_KEY = settings.NEWS_API_KEY  # NewsAPI ключ


# Модель для міста
class CityRequest(BaseModel):
    city: str


# Модель для валюти
class CurrencyRequest(BaseModel):
    base: str = "USD"
    target: Optional[str] = "UAH"


# Модель для новин
class NewsRequest(BaseModel):
    query: Optional[str] = None
    category: Optional[str] = "general"
    country: Optional[str] = "ua"


@app.get("/")
async def root():
    """Базовий маршрут, що вітає користувача"""
    return {"message": "Вітаємо в Інформаційному API. Доступні маршрути: /weather, /currency, /news"}


@app.get("/weather")
async def get_weather(city: str = "Kyiv"):
    """Отримати погоду для вказаного міста"""
    logger.info(f"Отримано запит на погоду для міста: {city}")

    try:
        async with httpx.AsyncClient() as client:
            api_url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": city,
                "appid": WEATHER_API_KEY,
                "units": "metric",
                "lang": "uk"
            }

            logger.info(f"Відправка запиту до OpenWeatherMap API: {api_url} з параметрами: {params}")
            response = await client.get(api_url, params=params)

            # Детальне логування статус-коду
            logger.info(f"Отримано відповідь від OpenWeatherMap API зі статусом: {response.status_code}")

            if response.status_code == 401:
                logger.error(f"Помилка авторизації (401) з OpenWeatherMap API. Перевірте ваш API ключ.")
                raise HTTPException(
                    status_code=500,
                    detail="Помилка авторизації з сервісом погоди. Перевірте API ключ."
                )

            response.raise_for_status()
            data = response.json()

            # Форматування відповіді
            result = {
                "city": data["name"],
                "country": data["sys"]["country"],
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "description": data["weather"][0]["description"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data["wind"]["speed"],
                "timestamp": datetime.now().isoformat()
            }

            # Без кешування

            logger.info(f"Успішно отримано дані про погоду для міста {city}")
            return result

    except httpx.HTTPStatusError as e:
        logger.error(f"Помилка HTTP при отриманні погоди: {str(e)}")
        error_message = f"Помилка HTTP {e.response.status_code} при отриманні даних про погоду"

        if e.response.status_code == 404:
            error_message = f"Місто {city} не знайдено"
            raise HTTPException(status_code=404, detail=error_message)
        elif e.response.status_code == 401:
            error_message = "Помилка авторизації з сервісом погоди. Перевірте API ключ."
            raise HTTPException(status_code=500, detail=error_message)
        else:
            raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Непередбачена помилка при отриманні погоди: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера при отриманні даних про погоду")


@app.get("/currency")
async def get_currency(base: str = "USD", target: str = "UAH"):
    """Отримати поточний курс валют"""
    logger.info(f"Отримано запит на курс валют: {base} до {target}")

    try:
        async with httpx.AsyncClient() as client:
            # Updated to a more reliable free currency API
            api_url = "https://open.er-api.com/v6/latest"
            params = {"base": base}

            logger.info(f"Відправка запиту до Exchange Rate API: {api_url} з параметрами: {params}")
            response = await client.get(api_url, params=params)

            # Детальне логування статус-коду
            logger.info(f"Отримано відповідь від Exchange Rate API зі статусом: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            # Check if the API response contains the necessary data
            if not data.get("rates") or target not in data.get("rates", {}):
                logger.error(f"Відсутні дані про курс валют у відповіді API: {data}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Не вдалося отримати курс валют для пари {base}/{target}"
                )

            # Форматування відповіді з перевіркою наявності ключів
            result = {
                "base": base,  # Use the input parameter instead of relying on the response
                "target": target,
                "rate": data.get("rates", {}).get(target),
                "date": data.get("time_last_update_utc", datetime.now().date().isoformat()),
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Успішно отримано курс валют {base} до {target}")
            return result

    except httpx.HTTPStatusError as e:
        logger.error(f"Помилка HTTP при отриманні курсу валют: {str(e)}")
        error_message = f"Помилка HTTP {e.response.status_code} при отриманні курсу валют"
        raise HTTPException(status_code=500, detail=error_message)
    except KeyError as e:
        logger.error(f"Помилка доступу до ключа у відповіді API: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка обробки даних: відсутній ключ {str(e)}")
    except Exception as e:
        logger.error(f"Непередбачена помилка при отриманні курсу валют: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера при отриманні курсу валют")


@app.get("/news")
async def get_news(query: str = None, category: str = "general", country: str = "ua"):
    """Отримати останні новини"""
    logger.info(f"Отримано запит на новини: query={query}, category={category}, country={country}")

    try:
        async with httpx.AsyncClient() as client:
            # Convert full country names to ISO 2-letter codes
            country_code = country.lower()
            # Map common country names/translations to their ISO codes
            country_map = {
                "україна": "ua",
                "сша": "us",
                "великобританія": "gb",
                "англія": "gb",
                "німеччина": "de",
                "франція": "fr",
                "італія": "it",
                "японія": "jp",
                "китай": "cn",
                "індія": "in",
                "бразилія": "br",
                "канада": "ca",
                "австралія": "au"
            }

            # Use the mapped country code if it exists
            if country_code in country_map:
                country_code = country_map[country_code]
            # Check if the input is already a valid 2-letter country code
            elif len(country_code) != 2:
                # Default to Ukraine if not a recognized country
                country_code = "ua"

            # Try different approaches to get news
            # First attempt: try with specific parameters
            articles = await try_get_news(client, query, category, country_code)

            # If no results, try without language restriction
            if not articles:
                logger.info("Спроба отримати новини без обмеження мови")
                articles = await try_get_news(client, query, category, country_code, language=None)

            # If still no results and we're looking for Ukrainian news, try a keyword search for "Ukraine"
            if not articles and country_code == "ua" and not query:
                logger.info("Спроба отримати новини за ключовим словом 'Україна'")
                articles = await try_get_news(client, "Україна", None, None, use_everything=True)

            # Last resort: get general headlines from a major country
            if not articles and not query:
                logger.info("Спроба отримати загальні світові новини")
                articles = await try_get_news(client, None, category, "us", language=None)

            result = {
                "query": query,
                "category": category,
                "country": country_code,
                "total_results": len(articles),
                "articles": articles,
                "timestamp": datetime.now().isoformat()
            }

            # Add a message if no articles were found after all attempts
            if not articles:
                logger.warning(f"Новини не знайдено за жодними параметрами пошуку")
                result[
                    "message"] = "Новини не знайдено. Спробуйте інші параметри пошуку або перевірте підключення до News API."

            logger.info(f"Успішно отримано {len(articles)} новин")
            return result

    except httpx.HTTPStatusError as e:
        logger.error(f"Помилка HTTP при отриманні новин: {str(e)}")
        error_message = f"Помилка HTTP {e.response.status_code} при отриманні новин"

        if e.response.status_code == 401:
            error_message = "Помилка авторизації з сервісом новин. Перевірте API ключ."
        elif e.response.status_code == 400:
            error_message = "Неправильні параметри запиту. Перевірте країну та категорію."

        raise HTTPException(status_code=500, detail=error_message)
    except Exception as e:
        logger.error(f"Непередбачена помилка при отриманні новин: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера при отриманні новин")


async def try_get_news(client, query=None, category=None, country=None, language="uk", use_everything=False):
    """Helper function to try getting news with different parameters"""
    params = {
        "apiKey": NEWS_API_KEY,
    }

    if language:
        params["language"] = language

    if country and not use_everything:
        params["country"] = country

    if category and not use_everything:
        params["category"] = category

    if query:
        if use_everything or not country:
            # For keyword searches without country constraint, use "everything" endpoint
            url = "https://newsapi.org/v2/everything"
            params["q"] = query
        else:
            # For top headlines with country and query
            url = "https://newsapi.org/v2/top-headlines"
            params["q"] = query
    else:
        # For pure browsing, use "top-headlines"
        url = "https://newsapi.org/v2/top-headlines"

    # If using everything endpoint without a query, add a default query
    if url == "https://newsapi.org/v2/everything" and "q" not in params:
        params["q"] = "world"

    # Ensure we have at least one filtering parameter for top-headlines
    if url == "https://newsapi.org/v2/top-headlines" and "country" not in params and "q" not in params:
        params["country"] = "us"  # Default to US if no filters

    logger.info(f"Спроба запиту до News API: {url} з параметрами: {params}")

    try:
        response = await client.get(url, params=params)
        logger.info(f"Отримано відповідь від News API зі статусом: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            articles = []

            for article in data.get("articles", [])[:10]:
                if article.get("title") and article.get("url"):
                    articles.append({
                        "title": article.get("title"),
                        "source": article.get("source", {}).get("name", "Невідоме джерело"),
                        "author": article.get("author"),
                        "description": article.get("description"),
                        "url": article.get("url"),
                        "published_at": article.get("publishedAt")
                    })

            logger.info(f"Знайдено {len(articles)} статей")
            return articles
        else:
            logger.warning(f"Невдалий запит до News API: статус {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Помилка при спробі отримати новини: {e}")
        return []


# Додатковий ендпоїнт для перевірки API ключів
@app.get("/check-api-keys")
async def check_api_keys():
    """Перевірити статус API ключів"""
    results = {}

    # Перевірка OpenWeatherMap API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "London", "appid": WEATHER_API_KEY}
            )
            results["weather_api"] = {
                "status": response.status_code,
                "valid": response.status_code == 200
            }
    except Exception as e:
        results["weather_api"] = {
            "status": "error",
            "valid": False,
            "error": str(e)
        }

    # Перевірка NewsAPI
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "apiKey": NEWS_API_KEY}
            )
            results["news_api"] = {
                "status": response.status_code,
                "valid": response.status_code == 200
            }
    except Exception as e:
        results["news_api"] = {
            "status": "error",
            "valid": False,
            "error": str(e)
        }

    return results


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
