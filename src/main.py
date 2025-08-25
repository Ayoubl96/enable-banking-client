from config import settings
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from utils import JWTHandler
from api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    if hasattr(app.state, 'enable_banking_client'):
        await app.state.enable_banking_client.http_client.aclose()

# Create FastAPI app
app = FastAPI(
    title="Enable Banking API Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routes
app.include_router(router)

if __name__ == "__main__":
    jwt_handler = JWTHandler(algorithm="RS256")
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
