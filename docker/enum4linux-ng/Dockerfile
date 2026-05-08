FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends smbclient ldap-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir enum4linux-ng
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["enum4linux-ng"]
CMD ["-h"]
