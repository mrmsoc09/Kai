FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git build-essential libssl-dev libffi-dev python3-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/cloudmapper
RUN git clone --depth 1 https://github.com/duo-labs/cloudmapper .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/cloudmapper
USER kaiuser
ENTRYPOINT ["python3", "cloudmapper.py"]
CMD ["--help"]
