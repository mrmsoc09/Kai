FROM perl:5.38-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends git libssl-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/nikto
RUN git clone --depth 1 https://github.com/sullo/nikto .
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/nikto
USER kaiuser
ENTRYPOINT ["perl", "/opt/nikto/program/nikto.pl"]
CMD ["-h"]
