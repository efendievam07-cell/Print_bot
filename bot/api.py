from fastapi import FastAPI

from bot.services.printer_api import router as printer_router


def create_app() -> FastAPI:
    app = FastAPI(title="Optop Printer API", version="1.0.0")
    app.include_router(printer_router)
    return app
