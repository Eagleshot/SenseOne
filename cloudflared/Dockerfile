FROM cloudflare/cloudflared:latest AS cloudflared

FROM alpine:3.20

RUN apk add --no-cache gettext

COPY --from=cloudflared /usr/local/bin/cloudflared /usr/local/bin/cloudflared
COPY config.template.yml /etc/cloudflared/config.template.yml
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
