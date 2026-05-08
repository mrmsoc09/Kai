FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/subbrute
RUN git clone --depth 1 https://github.com/TheRook/subbrute .
RUN pip install --no-cache-dir dnspython
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/subbrute
USER kaiuser
ENTRYPOINT ["python3", "subbrute.py"]
CMD ["-h"]
