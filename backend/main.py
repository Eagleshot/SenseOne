from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import PlainTextResponse

UPLOAD_DIR = Path("uploads")

def _sanitize_filename(raw_name: str) -> str:
    """Collapse disallowed characters so the saved filename remains predictable."""
    cleaned = re.sub(r"[^a-zA-Z0-9.\-_]", "_", raw_name)
    return cleaned or "default.jpg"


app = FastAPI()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


# Make a health endpoint for testing connectivity
@app.get("/health", response_class=PlainTextResponse)
async def health_check() -> PlainTextResponse:
    """Simple endpoint to verify the server is running."""
    return PlainTextResponse("OK")

@app.post("/upload", response_class=PlainTextResponse)
async def upload_image(request: Request, x_filename: Optional[str] = Header(default=None)) -> PlainTextResponse:
    """Receive raw image bytes and persist them under the provided (sanitized) filename."""
    filename = _sanitize_filename(x_filename or "default.jpg")
    file_path = UPLOAD_DIR / filename

    with file_path.open("wb") as target:
        async for chunk in request.stream():
            target.write(chunk)

    logging.info("File saved as %s", filename)
    return PlainTextResponse(f"File uploaded as {filename}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
