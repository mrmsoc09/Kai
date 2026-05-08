FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends hashcat && rm -rf /var/lib/apt/lists/*
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["hashcat"]
CMD ["--help"]
