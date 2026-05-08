FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir sqlmap
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["sqlmap"]
CMD ["--help"]
