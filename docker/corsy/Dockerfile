FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/corsy
RUN git clone --depth 1 https://github.com/s0md3v/Corsy .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || pip install --no-cache-dir .
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/corsy
USER kaiuser
ENTRYPOINT ["python3", "corsy.py"]
CMD ["--help"]
