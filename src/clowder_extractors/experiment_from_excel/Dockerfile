#FROM ghcr.io/re-mat/remat-clowder-extractor-base:latest
FROM remat-clowder-extractor-base:latest

# environemnt variables
ENV RABBITMQ_QUEUE="remat.experiment.from_excel"

COPY extractor_info.json ./

ENTRYPOINT ["experiment_from_excel"]


