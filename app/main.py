from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.usage import router as usage_router

app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="0.1.0",
)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(usage_router)


@app.get("/")
def root():
    return {
        "name": "Usage Metering & Billing Engine",
        "status": "running"
    }