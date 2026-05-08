FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir maigret
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["maigret"]
CMD ["--help"]
