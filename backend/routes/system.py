"""System and health check routes."""

import time

from fastapi import APIRouter, status, Response
from fastapi.responses import PlainTextResponse

from models import ClockResponse, ServiceInfoResponse

router = APIRouter(tags=["System"])


@router.get(
    "/",
    response_model=ServiceInfoResponse,
    summary="Service info",
    description="Return the service name and status.",
)
def root() -> ServiceInfoResponse:
    return ServiceInfoResponse(name="Eagleshot API", status="ok")


@router.get(
    "/health",
    response_class=PlainTextResponse,
    summary="Health check",
    description="Return `OK` when the service is available.",
)
def health() -> PlainTextResponse:
    return PlainTextResponse("OK")


@router.get(
    "/clock",
    response_model=ClockResponse,
    summary="Server clock",
    description="Return the current Unix timestamp for device clock synchronization.",
)
def server_clock() -> ClockResponse:
    return ClockResponse(unix_seconds=int(time.time()))


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)
