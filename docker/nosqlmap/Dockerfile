FROM python:3.8-slim-bookworm
RUN apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/nosqlmap
RUN git clone --depth 1 https://github.com/codingo/NoSQLMap .
RUN pip install "setuptools<60"
RUN python setup.py install
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/nosqlmap
USER kaiuser
ENTRYPOINT ["python3", "nosqlmap.py"]
CMD ["--help"]
