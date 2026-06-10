FROM python:3.8-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/tplmap
RUN git clone --depth 1 https://github.com/epinna/tplmap .
RUN pip install --no-cache-dir PyYAML==5.1.2 certifi==2018.10.15 chardet==3.0.4 idna==2.8 requests==2.22.0 urllib3==1.24.1
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/tplmap
USER kaiuser
ENTRYPOINT ["python3", "tplmap.py"]
CMD ["--help"]
