FROM ruby:3.2-slim
RUN gem install whatweb --no-document
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["whatweb"]
CMD ["--help"]
