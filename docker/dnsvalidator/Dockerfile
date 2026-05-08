FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/dnsvalidator
RUN git clone --depth 1 https://github.com/vortexau/dnsvalidator .
RUN pip install --no-cache-dir .
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/dnsvalidator
USER kaiuser
ENTRYPOINT ["dnsvalidator"]
CMD ["-h"]
