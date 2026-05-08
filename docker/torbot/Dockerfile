FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends tor && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir torbot
# NOTE: Tor service must be started before use: service tor start
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["torbot"]
CMD ["--help"]
