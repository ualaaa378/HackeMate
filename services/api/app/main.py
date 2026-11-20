from fastapi import FastAPI

from app import __version__
from app.config import get_settings

app = FastAPI(title="HackeMate api", version=__version__)


@app.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version or __version__}
