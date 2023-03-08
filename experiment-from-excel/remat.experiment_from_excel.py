#!/usr/bin/env python

import hashlib
import logging
import os
import requests
import certifi
import json

from openpyxl.worksheet.worksheet import Worksheet
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
from openpyxl import load_workbook


class ExperimentFromExcel(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the exctractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.download

    def excel_to_json(self, path):
        wb = load_workbook(filename=path)
        inputs = {}

        for sheet in wb.sheetnames:
            inputs[sheet] = []
            ws = wb[sheet]
            headers = [col.value for col in list(ws.rows)[0]]
            for row in ws.iter_rows(min_row=2):
                input_properties = {key: cell.value for key, cell in zip(headers, row)}
                inputs[sheet].append(input_properties)

        return {"inputs": inputs}

    def process_message(self, connector, host, secret_key, resource, parameters):
        logger = logging.getLogger('__main__')
        experiment = self.excel_to_json(resource['local_paths'][0])
        logger.debug(experiment)

        # store results as metadata
        metadata = {
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "dataset_id": resource['parent'].get('id', None),
            "content": experiment,
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "api/extractors/" + self.extractor_info['name']
            }
        }

        pyclowder.datasets.upload_metadata(connector, host, secret_key,
                                           resource['parent'].get('id', None), metadata)


if __name__ == "__main__":
    extractor = ExperimentFromExcel()
    extractor.start()
