FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

EXPOSE 3000

# --proxy-headers lets uvicorn trust X-Forwarded-Proto/-For so request.url.scheme
# and request.client.host are correct behind the tunnel (required for both
# APP_REQUIRE_HTTPS and the per-IP login throttle). Which sources are trusted is
# controlled by the FORWARDED_ALLOW_IPS env var (uvicorn reads it natively;
# default 127.0.0.1). It MUST be scoped to the proxy/cloudflared subnet — see
# docker-compose.yml. Never set it to "*": that lets any client spoof those
# headers and bypass HTTPS enforcement and IP throttling.
CMD ["uvicorn", "main:create_app", "--factory", "--host", "0.0.0.0", "--port", "3000", "--proxy-headers"]
