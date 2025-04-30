from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field


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
