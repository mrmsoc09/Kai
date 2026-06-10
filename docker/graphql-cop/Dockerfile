FROM python:3.12-slim-bookworm AS builder
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    git clone --depth 1 https://github.com/dolevf/graphql-cop.git /app && \
    rm -rf /app/.git

FROM python:3.12-slim-bookworm
COPY --from=builder /app /app
WORKDIR /app
RUN pip install --no-cache-dir -r requirements.txt
RUN echo '#!/bin/sh' > /usr/local/bin/graphql-cop && \
    echo 'exec python3 /app/graphql-cop.py "$@"' >> /usr/local/bin/graphql-cop && \
    chmod +x /usr/local/bin/graphql-cop
RUN addgroup --system kaigroup && adduser --system --ingroup kaigroup --no-create-home kaiuser
USER kaiuser
ENTRYPOINT ["graphql-cop"]
CMD ["--help"]
