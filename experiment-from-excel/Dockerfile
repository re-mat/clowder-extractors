FROM python:3.10

ARG VERSION="unknown"
ARG BUILDNUMBER="unknown"
ARG GITSHA1="unknown"

# environemnt variables
ENV VERSION=${VERSION} \
    BUILDNUMBER=${BUILDNUMBER} \
    GITSHA1=${GITSHA1} \
    RABBITMQ_QUEUE="remat.experiment.from_excel"

WORKDIR /extractor
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY remat.experiment_from_excel.py extractor_info.json chemistry.py ./
CMD python remat.experiment_from_excel.py