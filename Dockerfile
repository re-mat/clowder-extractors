FROM python:3.10


ARG VERSION="unknown"
ARG BUILDNUMBER="unknown"
ARG GITSHA1="unknown"


WORKDIR /extractor
#COPY requirements.txt ./
#RUN pip install -r requirements.txt
#
#COPY remat.csv_stripper.py extractor_info.json ./


# Copy the root project files
COPY pyproject.toml ./
COPY src ./src


RUN pip install .
