FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir graphql-cop
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["graphql-cop"]
CMD ["--help"]
