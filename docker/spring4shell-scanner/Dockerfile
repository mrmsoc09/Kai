FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir spring4shell-scan 2>/dev/null || \
    pip install --no-cache-dir requests
WORKDIR /opt/spring4shell
RUN git clone --depth 1 https://github.com/fullhunt/spring4shell-scan . 2>/dev/null || true
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser \
 && chown -R kaiuser:kaigroup /opt/spring4shell
USER kaiuser
ENTRYPOINT ["python3", "spring4shell-scan.py"]
CMD ["-h"]
