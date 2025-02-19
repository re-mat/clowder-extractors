# Use the Qualified Base Image only if you are building the image through the CI/CD pipeline or if the base image is published
# If you are building the image locally, use the Unqualified Base Image
FROM ghcr.io/re-mat/remat-clowder-extractor-base:latest
# environment variables
ENV RABBITMQ_QUEUE="remat.experiment.from_excel"

COPY extractor_info.json ./

ENTRYPOINT ["experiment_from_excel"]
