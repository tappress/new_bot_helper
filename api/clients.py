import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

import httpx

from api.exceptions import ResourceNotFoundError, APIKeyError, ExternalAPIError
from api.schemas import WeatherResponse, CurrencyResponse, NewsArticle
from settings import settings

logger = logging.getLogger(__name__)


# Weather API Client
async def get_weather_data(city: str) -> WeatherResponse:
    """Fetch weather data from OpenWeatherMap API"""
    logger.info(f"Requesting weather data for city: {city}")

    async with httpx.AsyncClient() as client:
        api_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": city,
            "appid": settings.WEATHER_API_KEY,
            "units": "metric",
            "lang": "uk",
        }

        try:
            logger.info(f"Sending request to OpenWeatherMap API with params: {params}")
            response = await client.get(api_url, params=params)

            logger.info(
                f"Received response from OpenWeatherMap API with status: {response.status_code}"
            )

            if response.status_code == 401:
                logger.error("Authentication error (401) with OpenWeatherMap API")
                raise APIKeyError("weather")

            response.raise_for_status()
            data = response.json()

            # Format response
            result = WeatherResponse(
                city=data["name"],
                country=data["sys"]["country"],
                temperature=data["main"]["temp"],
                feels_like=data["main"]["feels_like"],
                description=data["weather"][0]["description"],
                humidity=data["main"]["humidity"],
                pressure=data["main"]["pressure"],
                wind_speed=data["wind"]["speed"],
                timestamp=datetime.now(),
            )

            logger.info(f"Successfully retrieved weather data for city {city}")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while fetching weather data: {str(e)}")

            if e.response.status_code == 404:
                raise ResourceNotFoundError("City", city)
            elif e.response.status_code == 401:
                raise APIKeyError("weather")
            else:
                raise ExternalAPIError("weather", e.response.status_code)

        except Exception as e:
            logger.error(f"Unexpected error while fetching weather data: {str(e)}")
            raise ExternalAPIError("weather")


# Currency API Client
async def get_currency_rate(base: str, target: str) -> CurrencyResponse:
    """Fetch currency exchange rate data"""
    logger.info(f"Requesting currency rate: {base} to {target}")

    async with httpx.AsyncClient() as client:
        api_url = "https://open.er-api.com/v6/latest"
        params = {"base": base}

        try:
            logger.info(f"Sending request to Exchange Rate API with params: {params}")
            response = await client.get(api_url, params=params)

            logger.info(
                f"Received response from Exchange Rate API with status: {response.status_code}"
            )

            response.raise_for_status()
            data = response.json()

            # Check if the API response contains the necessary data
            if not data.get("rates") or target not in data.get("rates", {}):
                logger.error(f"Missing currency rate data in API response: {data}")
                raise ResourceNotFoundError("Currency rate", f"{base}/{target}")

            # Format response
            result = CurrencyResponse(
                base=base,
                target=target,
                rate=data.get("rates", {}).get(target),
                date=data.get(
                    "time_last_update_utc", datetime.now().date().isoformat()
                ),
                timestamp=datetime.now(),
            )

            logger.info(f"Successfully retrieved currency rate {base} to {target}")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error while fetching currency rate: {str(e)}")
            raise ExternalAPIError("currency exchange rate", e.response.status_code)

        except Exception as e:
            logger.error(f"Unexpected error while fetching currency rate: {str(e)}")
            raise ExternalAPIError("currency exchange rate")


# News API Client
# Map common country names/translations to their ISO codes
COUNTRY_MAP = {
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
    "австралія": "au",
}


def normalize_country_code(country: str) -> str:
    """Convert country name to ISO 2-letter code"""
    country_code = country.lower()

    # Use the mapped country code if it exists
    if country_code in COUNTRY_MAP:
        return COUNTRY_MAP[country_code]
    # Check if the input is already a valid 2-letter country code
    elif len(country_code) == 2:
        return country_code
    # Default to Ukraine if not a recognized country
    else:
        return "ua"


async def try_get_news(
    client: httpx.AsyncClient,
    query: Optional[str] = None,
    category: Optional[str] = None,
    country: Optional[str] = None,
    language: Optional[str] = "uk",
    use_everything: bool = False,
) -> List[NewsArticle]:
    """Helper function to try getting news with different parameters"""
    params: Dict[str, Any] = {
        "apiKey": settings.NEWS_API_KEY,
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
    if (
        url == "https://newsapi.org/v2/top-headlines"
        and "country" not in params
        and "q" not in params
    ):
        params["country"] = "us"  # Default to US if no filters

    logger.info(f"Trying request to News API: {url} with params: {params}")

    try:
        response = await client.get(url, params=params)
        logger.info(
            f"Received response from News API with status: {response.status_code}"
        )

        if response.status_code == 401:
            logger.error("Authentication error (401) with News API")
            raise APIKeyError("news")

        if response.status_code == 200:
            data = response.json()
            articles = []

            for article in data.get("articles", [])[:10]:
                if article.get("title") and article.get("url"):
                    articles.append(
                        NewsArticle(
                            title=article.get("title"),
                            source=article.get("source", {}).get(
                                "name", "Unknown source"
                            ),
                            author=article.get("author"),
                            description=article.get("description"),
                            url=article.get("url"),
                            published_at=article.get("publishedAt"),
                        )
                    )

            logger.info(f"Found {len(articles)} articles")
            return articles
        else:
            logger.warning(
                f"Unsuccessful request to News API: status {response.status_code}"
            )
            return []
    except Exception as e:
        logger.error(f"Error trying to get news: {e}")
        return []


async def get_news_articles(
    query: Optional[str] = None,
    category: Optional[str] = "general",
    country: Optional[str] = "ua",
) -> List[NewsArticle]:
    """Fetch news articles with various fallback strategies"""
    logger.info(
        f"Requesting news: query={query}, category={category}, country={country}"
    )

    country_code = normalize_country_code(country)

    async with httpx.AsyncClient() as client:
        # Try different approaches to get news
        # First attempt: try with specific parameters
        articles = await try_get_news(client, query, category, country_code)

        # If no results, try without language restriction
        if not articles:
            logger.info("Trying to get news without language restriction")
            articles = await try_get_news(
                client, query, category, country_code, language=None
            )

        # If still no results and we're looking for Ukrainian news, try a keyword search for "Ukraine"
        if not articles and country_code == "ua" and not query:
            logger.info("Trying to get news with keyword 'Ukraine'")
            articles = await try_get_news(
                client, "Україна", None, None, use_everything=True
            )

        # Last resort: get general headlines from a major country
        if not articles and not query:
            logger.info("Trying to get general world news")
            articles = await try_get_news(client, None, category, "us", language=None)

        return articles