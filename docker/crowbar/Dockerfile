FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git openvpn nmap && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/crowbar
RUN git clone --depth 1 https://github.com/galkan/crowbar .
RUN pip install --no-cache-dir -r requirements.txt 2>/dev/null || true
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/crowbar
USER kaiuser
ENTRYPOINT ["python3", "crowbar.py"]
CMD ["-h"]
