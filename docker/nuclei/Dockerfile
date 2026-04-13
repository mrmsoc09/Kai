FROM projectdiscovery/nuclei:latest

LABEL org.opencontainers.image.title="K1 Nuclei Isolated Scanner"
LABEL org.opencontainers.image.description="Isolated nuclei runtime for K1 vulnerability automation"

WORKDIR /workspace

ENV NUCLEI_TEMPLATES_DIRECTORY=/root/nuclei-templates

RUN mkdir -p /workspace/input /workspace/output "${NUCLEI_TEMPLATES_DIRECTORY}"

ENTRYPOINT ["nuclei"]
CMD ["-h"]
