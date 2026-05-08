FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir bloodhound
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["bloodhound-python"]
CMD ["-h"]
