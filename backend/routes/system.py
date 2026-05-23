"""System and health check routes."""

import time

from fastapi import APIRouter, status, Response
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["System"])


@router.get(
    "/",
    summary="Service info",
    description="Tiny JSON ping returning the service name. Unauthenticated.",
)
def root() -> dict:
    return {"name": "Eagleshot API", "status": "ok"}


@router.get(
    "/health",
    response_class=PlainTextResponse,
    summary="Health check",
    description=(
        "Plain-text liveness probe for load balancers and uptime monitors. "
        "Always returns `OK` with status 200 while the process is up."
    ),
)
def health() -> PlainTextResponse:
    return PlainTextResponse("OK")


@router.get(
    "/v1/server-time",
    summary="Server time",
    description=(
        "Return the server's current wall-clock time as unix seconds. "
        "Unauthenticated.\n\n"
        "Devices without a reliable RTC fetch this once at boot so they can sign "
        "subsequent requests with a timestamp the server will accept "
        "(the verifier allows +-300 s of skew). Devices typically capture the "
        "server time alongside a monotonic counter and re-sync every 12 hours."
    ),
)
def server_time() -> dict:
    return {"unixSeconds": int(time.time())}


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
