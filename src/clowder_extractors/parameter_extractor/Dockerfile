# Use the Qualified Base Image only if you are building the image through the CI/CD pipeline or if the base image is published
# If you are building the image locally, use the Unqualified Base Image
FROM ghcr.io/re-mat/remat-clowder-extractor-base:latest
# environment variables
ENV RABBITMQ_QUEUE="remat.parameters.from_txt"

COPY extractor_info.json ./
ENTRYPOINT ["parameter_extractor"]
