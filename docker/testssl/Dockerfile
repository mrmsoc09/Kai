FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends git curl openssl dnsutils bsdmainutils && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/testssl
RUN git clone --depth 1 https://github.com/drwetter/testssl.sh .
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/testssl
USER kaiuser
ENTRYPOINT ["/opt/testssl/testssl.sh"]
CMD ["-h"]
