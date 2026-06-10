FROM debian:bookworm-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends git curl openssl dnsutils bsdmainutils && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/testssl
RUN git config --global http.sslVerify false
RUN for i in $(seq 1 5); do git clone --depth 1 https://github.com/drwetter/testssl.sh . && break; sleep 5; done
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/testssl
USER kaiuser
ENTRYPOINT ["/opt/testssl/testssl.sh"]
CMD ["-h"]
