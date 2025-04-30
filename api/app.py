import logging

from fastapi import FastAPI

from api.routes import weather_router, currency_router, news_router, health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

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
