FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir apkleaks
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["apkleaks"]
CMD ["-h"]
