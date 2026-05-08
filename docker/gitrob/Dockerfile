FROM alpine:latest
RUN echo '#!/bin/sh' > /usr/local/bin/gitrob \
 && echo 'echo "gitrob is archived. Use trufflehog or gitleaks for git secrets scanning."' >> /usr/local/bin/gitrob \
 && chmod +x /usr/local/bin/gitrob
RUN addgroup -S kaigroup && adduser -S -G kaigroup -H -D kaiuser
USER kaiuser
ENTRYPOINT ["/usr/local/bin/gitrob"]
