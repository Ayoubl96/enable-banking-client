from config import settings
import uvicorn
from fastapi import FastAPI
from utils import JWTHandler
from api.routes import router

# Create FastAPI app
app = FastAPI(
    title="Enable Banking API Service",
    version="1.0.0",
)

# Include routes
app.include_router(router)

@app.on_event("shutdown")
async def shutdown_event():
    # Close HTTP client if it exists
    if hasattr(app.state, 'enable_banking_client'):
        await app.state.enable_banking_client.http_client.aclose()

if __name__ == "__main__":
    jwt_handler = JWTHandler(algorithm="RS256")
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
