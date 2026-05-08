FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends john && rm -rf /var/lib/apt/lists/*
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["john"]
CMD ["--help"]
