FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git gcc python3-dev libffi-dev libpcap-dev build-essential && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir kube-hunter
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["kube-hunter"]
CMD ["--help"]
