# Description: Base image for Clowder Extractors
FROM python:3.10


ARG VERSION="unknown"
ARG BUILDNUMBER="unknown"
ARG GITSHA1="unknown"


WORKDIR /extractor


# Copy the root project files
COPY pyproject.toml ./
COPY src ./src

# Run Python package
RUN pip install .
