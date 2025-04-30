import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends

from api.clients import get_weather_data, get_currency_rate, get_news_articles
from api.schemas import (
    WeatherResponse,
    CityRequest,
    CurrencyResponse,
    CurrencyRequest,
    NewsResponse,
    NewsRequest,
    APIKeyCheckResponse,
    APIKeyStatus,
)
from settings import settings

logger = logging.getLogger(__name__)

# Create API routers
weather_router = APIRouter(tags=["Weather"])
currency_router = APIRouter(tags=["Currency"])
news_router = APIRouter(tags=["News"])
health_router = APIRouter(prefix="/health", tags=["Health"])


# Weather route
@weather_router.get("/weather", response_model=WeatherResponse)
async def get_weather(city_request: CityRequest = Depends()):
    """Get weather for the specified city"""
    return await get_weather_data(city_request.city)


# Currency route
@currency_router.get("/currency", response_model=CurrencyResponse)
async def get_currency(currency_request: CurrencyRequest = Depends()):
    """Get current currency exchange rate"""
    return await get_currency_rate(currency_request.base, currency_request.target)


# News route
@news_router.get("/news", response_model=NewsResponse)
async def get_news(news_request: NewsRequest = Depends()):
    """Get latest news"""
    articles = await get_news_articles(
        news_request.query, news_request.category, news_request.country
    )

    result = NewsResponse(
        query=news_request.query,
        category=news_request.category,
        country=news_request.country,
        total_results=len(articles),
        articles=articles,
        timestamp=datetime.now(),
    )

    # Add a message if no articles were found after all attempts
    if not articles:
        logger.warning(f"No news found for any search parameters")
        result.message = "No news found. Try different search parameters or check News API connection."

    logger.info(f"Successfully retrieved {len(articles)} news articles")
    return result


# Health check route
@health_router.get("/check-api-keys", response_model=APIKeyCheckResponse)
async def check_api_keys():
    """Check API keys status"""
    results = {}

    # Check OpenWeatherMap API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": "London", "appid": settings.WEATHER_API_KEY},
            )
            results["weather_api"] = APIKeyStatus(
                status=response.status_code, valid=response.status_code == 200
            )
    except Exception as e:
        results["weather_api"] = APIKeyStatus(status="error", valid=False, error=str(e))

    # Check NewsAPI
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "apiKey": settings.NEWS_API_KEY},
            )
            results["news_api"] = APIKeyStatus(
                status=response.status_code, valid=response.status_code == 200
            )
    except Exception as e:
        results["news_api"] = APIKeyStatus(status="error", valid=False, error=str(e))

    return APIKeyCheckResponse(**results)
