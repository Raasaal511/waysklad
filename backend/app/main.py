from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app import router as main_router
from app.infrastructure.files import UPLOAD_DIR
from app.presentation.errors import register_exception_handlers

app = FastAPI(title="ВайСклад API", version="0.1.0")

app.include_router(main_router)
register_exception_handlers(app)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
