FROM python:3.10

ARG VERSION="unknown"
ARG BUILDNUMBER="unknown"
ARG GITSHA1="unknown"

# environemnt variables
ENV VERSION=${VERSION} \
    BUILDNUMBER=${BUILDNUMBER} \
    GITSHA1=${GITSHA1} \
    RABBITMQ_QUEUE="remat.parameters.from_txt"

WORKDIR /extractor
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY remat.parameter_extractor.py extractor_info.json ./
CMD python remat.parameter_extractor.py