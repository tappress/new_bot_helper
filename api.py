import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException, APIRouter, Depends
from pydantic import BaseModel, Field
from settings import settings


#############################################################################
# CONFIGURATION
#############################################################################

logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )
logger = logging.getLogger(__name__)


#############################################################################
# CUSTOM EXCEPTIONS
#############################################################################


class APIKeyError(HTTPException):
    def __init__(self, service: str):
        super().__init__(
            status_code=500,
            detail=f"Authentication error with {service} service. Please check the API key.",
        )


class ResourceNotFoundError(HTTPException):
    def __init__(self, resource: str, query: str):
        super().__init__(status_code=404, detail=f"{resource} '{query}' not found")


class ExternalAPIError(HTTPException):
    def __init__(self, service: str, status_code: int = 500):
        super().__init__(
            status_code=status_code,
            detail=f"Error communicating with {service} service",
        )


#############################################################################
# DATA MODELS
#############################################################################


# Request Models
class CityRequest(BaseModel):
    city: str = Field(default="Kyiv", description="City name")


class CurrencyRequest(BaseModel):
    base: str = Field(default="USD", description="Base currency code")
    target: str = Field(default="UAH", description="Target currency code")


class NewsRequest(BaseModel):
    query: Optional[str] = Field(default=None, description="Search query")
    category: str = Field(default="general", description="News category")
    country: str = Field(default="ua", description="Country code")


# Response Models
class WeatherResponse(BaseModel):
    city: str
    country: str
    temperature: float
    feels_like: float
    description: str
    humidity: int
    pressure: int
    wind_speed: float
    timestamp: datetime


class CurrencyResponse(BaseModel):
    base: str
    target: str
    rate: float
    date: str
    timestamp: datetime


class NewsArticle(BaseModel):
    title: str
    source: str
    author: Optional[str] = None
    description: Optional[str] = None
    url: str
    published_at: Optional[str] = None


class NewsResponse(BaseModel):
    query: Optional[str] = None
    category: str
    country: str
    total_results: int
    articles: List[NewsArticle]
    timestamp: datetime
    message: Optional[str] = None


class APIKeyStatus(BaseModel):
    status: Any
    valid: bool
    error: Optional[str] = None


class APIKeyCheckResponse(BaseModel):
    weather_api: APIKeyStatus
    news_api: APIKeyStatus


#############################################################################
# API CLIENTS
#############################################################################


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


#############################################################################
# API ROUTES
#############################################################################

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


#############################################################################
# MAIN APPLICATION
#############################################################################

# Create FastAPI application
app = FastAPI(
    title="Information API",
    description="API for retrieving weather, currency rates, and news",
)

# Include routers
app.include_router(weather_router)
app.include_router(currency_router)
app.include_router(news_router)
app.include_router(health_router)


@app.get("/")
async def root():
    """Base route that welcomes the user"""
    return {
        "message": "Welcome to the Information API",
        "available_routes": [
            "/weather",
            "/currency",
            "/news",
            "/health/check-api-keys",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
