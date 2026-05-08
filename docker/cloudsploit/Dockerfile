FROM node:20-slim
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/cloudsploit
RUN git clone --depth 1 https://github.com/aquasecurity/cloudsploit .
RUN npm install --no-save
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/cloudsploit
USER kaiuser
ENTRYPOINT ["node", "index.js"]
CMD ["--help"]
