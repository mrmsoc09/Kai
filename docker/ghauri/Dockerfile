FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    pip install --no-cache-dir git+https://github.com/r0oth3x49/ghauri.git && \
    apt-get purge -y --auto-remove git && \
    rm -rf /var/lib/apt/lists/*
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["ghauri"]
CMD ["--help"]
