import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
from fastapi import FastAPI, HTTPException, APIRouter, Depends
from pydantic import BaseModel, Field
from settings import settings



#############################################################################
# API CLIENTS
#############################################################################




#############################################################################
# API ROUTES
#############################################################################



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
