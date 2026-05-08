FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir prowler
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["prowler"]
CMD ["--help"]
