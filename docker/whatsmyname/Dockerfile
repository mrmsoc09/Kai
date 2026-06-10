FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/whatsmyname
RUN git clone --depth 1 https://github.com/WebBreacher/WhatsMyName .
RUN pip install --no-cache-dir requests colorama
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/whatsmyname
USER kaiuser
ENTRYPOINT ["python3", "web_accounts_list.py"]
CMD ["--help"]
