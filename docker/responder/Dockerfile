FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/responder
RUN git clone --depth 1 https://github.com/lgandx/Responder .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
# NOTE: Responder requires --network=host and privileged mode to function
# cap_add: [NET_ADMIN, NET_RAW] required in docker-compose
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/responder
USER kaiuser
ENTRYPOINT ["python3", "Responder.py"]
CMD ["-h"]
