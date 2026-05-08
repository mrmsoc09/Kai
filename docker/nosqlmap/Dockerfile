FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/nosqlmap
RUN git clone --depth 1 https://github.com/codingo/NoSQLMap .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || pip install --no-cache-dir .
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/nosqlmap
USER kaiuser
ENTRYPOINT ["python3", "nosqlmap.py"]
CMD ["--help"]
