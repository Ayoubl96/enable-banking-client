from config import settings
import uvicorn
from fastapi import FastAPI
from utils import JWTHandler

# Create FastAPI app
app = FastAPI(
    title="Enable Banking API Service",
    version="1.0.0",
)

if __name__ == "__main__":
    jwt_handler = JWTHandler(algorithm="RS256")
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
