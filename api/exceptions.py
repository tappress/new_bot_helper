from fastapi import HTTPException


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
