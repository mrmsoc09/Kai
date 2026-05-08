FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends ldap-utils && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir ldapdomaindump
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["ldapdomaindump"]
CMD ["--help"]
