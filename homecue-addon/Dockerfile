FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH
ARG BUILD_VERSION

RUN apk add --no-cache python3 py3-cryptography

COPY run.sh /run.sh
COPY server.py /app/server.py
RUN chmod a+x /run.sh

LABEL io.hass.type="app" \
      io.hass.version="${BUILD_VERSION}" \
      io.hass.arch="${BUILD_ARCH}"

CMD ["/run.sh"]
