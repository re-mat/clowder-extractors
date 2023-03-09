#!/usr/bin/env python

import logging
import os
import csv
import tempfile
import typing
from tempfile import NamedTemporaryFile

from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files


def is_float(element: any) -> bool:
    """
    Check whether a string represents a valid floating point number
    Copied from https://stackoverflow.com/a/20929881
    :param element:
    :return: boolean
    """
    if element is None:
        return False
    try:
        float(element)
        return True
    except ValueError:
        return False


def extract_parameters(path, stripped_file: typing.TextIO):
    params = {}
    stripped_csv = csv.writer(stripped_file)
    stripped_csv.writerow(["Time", "Temperature", "Heat Flow (Normalized)"])

    with open(path, 'r') as experiment_file:
        reader = csv.reader(experiment_file)
        for row in reader:
            if row == ['[step]']:
                break
            params[row[0]] = row[1]

        # Skip over the step headers
        for row2 in reader:
            # Valid rows contain all numbers. Others are headers or comments
            if not any([not is_float(val) for val in row2]) and row2:
                stripped_csv.writerow(row2)
    return params


class CSVStripper(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the extractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

    def check_message(self, connector, host, secret_key, resource, parameters):
        # Don't operate on the output of this extractor. Only the raw input files from
        # the instrument
        if resource['name'] == "DSC_Curve.csv":
            return CheckMessage.ignore
        else:
            return CheckMessage.download

    def process_message(self, connector, host, secret_key, resource, parameters):
        logger = logging.getLogger('__main__')

        with tempfile.TemporaryDirectory() as tmpdirname:
            dsc_file_path = os.path.join(tmpdirname, "DSC_Curve.csv")
            with open(dsc_file_path, 'w') as dsc_file:
                dsc_file = open(os.path.join(tmpdirname, "DSC_Curve.csv"), 'w')
                parameters = extract_parameters(
                    resource['local_paths'][0],
                    dsc_file)

            logger.debug(parameters)

            # Upload the stripped CSV file
            uploaded_id = pyclowder.files.upload_to_dataset(connector, host, secret_key,
                                                            resource['parent'].get('id', None),
                                                            dsc_file_path)

            # Attach metadata stripped from the source file
            metadata = {
                "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
                "dataset_id": resource['parent'].get('id', None),
                "content": parameters,
                "agent": {
                    "@type": "cat:extractor",
                    "extractor_id": host + "api/extractors/" + self.extractor_info['name']
                }
            }

            pyclowder.files.upload_metadata(connector, host, secret_key, uploaded_id, metadata)


if __name__ == "__main__":
    extractor = CSVStripper()
    extractor.start()
