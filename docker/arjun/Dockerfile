FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir arjun
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["arjun"]
CMD ["--help"]
