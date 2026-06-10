FROM python:3.12-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git python3-dev samba-common-bin smbclient python3-ldap3 python3-yaml python3-impacket && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/enum4linux-ng
RUN git clone --depth 1 https://github.com/cddmp/enum4linux-ng .
RUN pip install --no-cache-dir -r requirements.txt
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser && chown -R kaiuser:kaigroup /opt/enum4linux-ng
USER kaiuser
ENTRYPOINT ["python3", "enum4linux-ng.py"]
CMD ["--help"]
