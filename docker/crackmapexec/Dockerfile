FROM python:3.12-slim-bookworm

# Install system dependencies
RUN apt-get update -qq && apt-get install -y --no-install-recommends gcc g++ make autoconf libtool libffi-dev libxml2-dev libxslt-dev libssl-dev openssl python3-dev curl git unzip libkrb5-dev && rm -rf /var/lib/apt/lists/*

# Install Rust (required for certain dependencies like aardwolf)
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /opt/crackmapexec
# Clone the NetExec repository (formerly CrackMapExec)
RUN git clone --depth 1 https://github.com/Pennyw0rth/NetExec.git .

# Install NetExec
RUN pip install --no-cache-dir .

RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser && chown -R kaiuser:kaigroup /opt/crackmapexec
USER kaiuser
ENTRYPOINT ["nxc"]
CMD ["--help"]
