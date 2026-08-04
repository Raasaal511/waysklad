from fastapi import FastAPI

from app import router as main_router

app = FastAPI(title="ВайСклад API", version="0.1.0")

app.include_router(main_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}



