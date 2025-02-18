#FROM ghcr.io/re-mat/remat-clowder-extractor-base:latest
FROM remat-clowder-extractor-base:latest


# environemnt variables
ENV RABBITMQ_QUEUE="remat.parameters.from_txt"

COPY extractor_info.json ./
ENTRYPOINT ["parameter_extractor"]