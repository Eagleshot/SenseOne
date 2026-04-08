"""System and health check routes."""

from fastapi import APIRouter, status, Response
from fastapi.responses import PlainTextResponse

router = APIRouter(tags=["System"])


@router.get(
    "/",
    summary="Get Service Info",
    description="Return a small metadata payload for the API service.",
)
def root() -> dict:
    """Return service metadata."""
    return {"name": "Eagleshot API", "status": "ok"}


@router.get(
    "/health",
    response_class=PlainTextResponse,
    summary="Health Check",
    description="Return a simple liveness response for health checks and load balancers.",
)
def health() -> PlainTextResponse:
    """Return health status."""
    return PlainTextResponse("OK")


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Return 204 for favicon requests."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)
