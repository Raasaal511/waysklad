from fastapi import FastAPI

from app import router as main_router
from app.presentation.errors import register_exception_handlers

app = FastAPI(title="ВайСклад API", version="0.1.0")

app.include_router(main_router)
register_exception_handlers(app)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
