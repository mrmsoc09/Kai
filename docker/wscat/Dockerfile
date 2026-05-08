FROM node:20-alpine
RUN npm install -g wscat
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["wscat"]
CMD ["--help"]
