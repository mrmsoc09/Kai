FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git libssl-dev libffi-dev build-essential libmariadb-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/patator
RUN git clone --depth 1 https://github.com/lanjelot/patator .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/patator
USER kaiuser
ENTRYPOINT ["python3", "patator.py"]
CMD ["--help"]
