from fastapi import FastAPI

from app.api.health import router as health_router


app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="0.1.0",
)

app.include_router(health_router)


@app.get("/")
def root():
    return {
        "name": "Usage Metering & Billing Engine",
        "status": "running",
    }