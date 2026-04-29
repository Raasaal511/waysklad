import uvicorn

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.api.v1 import router as router_v1
from src.exceptions import ModelNotFound

app = FastAPI()


@app.exception_handler(ModelNotFound)
async def product_not_found_exception(request, exc: ModelNotFound):
    return JSONResponse(
         status_code=404,
         content={"error": exc.message}
    )

app.include_router(router_v1)


if __name__ == "__main__":
    uvicorn.run(app=app)
