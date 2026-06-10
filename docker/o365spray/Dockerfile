FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/o365spray
RUN git clone --depth 1 https://github.com/0xZDH/o365spray .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["python3", "o365spray.py"]
CMD ["--help"]
