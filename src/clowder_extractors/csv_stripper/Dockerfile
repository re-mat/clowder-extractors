#FROM ghcr.io/re-mat/remat-clowder-extractor-base
FROM remat-clowder-extractor-base:latest


ENV RABBITMQ_QUEUE="remat.DSC.csv_stripper"

COPY extractor_info.json ./

ENTRYPOINT ["csv_stripper"]

