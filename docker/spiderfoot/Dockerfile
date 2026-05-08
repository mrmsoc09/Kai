FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/spiderfoot
RUN git clone --depth 1 https://github.com/smicallef/spiderfoot .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/spiderfoot
USER kaiuser
EXPOSE 5001
ENTRYPOINT ["python3", "sf.py"]
CMD ["-l", "0.0.0.0:5001"]
