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


def read_inputs_from_worksheet(ws: Worksheet) -> dict:
    inputs = []
    headers = [col.value for col in list(ws.rows)[0]]
    for row in ws.iter_rows(min_row=2):
        input_properties = {key: cell.value for key, cell in zip(headers, row)}
        inputs.append(input_properties)

    return inputs


def read_procedure_from_worksheet(ws: Worksheet) -> dict:
    procedure = {}
    for row in ws.iter_rows():
        procedure[row[0].value] = row[1].value

    return procedure


def read_thermochemical_from_worksheet(ws: Worksheet) -> dict:
    values = {}
    for row in ws.iter_rows():
        if row[0].style == "CurePhase":
            cure_phase = row[0].value
            values[cure_phase] = {
                "Delta HR Baseline": {}
            }
        elif row[0].style == "DeltaHRBaseline":
            pass
        elif row[0].style == "DeltaHRBaselineVal":
            property_name = row[0].value
            values[cure_phase]["Delta HR Baseline"][property_name] = row[1].value
        else:
            property_name = row[0].value
            values[cure_phase][property_name] = row[1].value
    return values


def excel_to_json(path):
    wb = load_workbook(filename=path)
    inputs = {}

    for sheet in wb.sheetnames:
        if sheet == "thermochemical":
            thermochemical = read_thermochemical_from_worksheet(wb[sheet])
        elif sheet == "procedure":
            procedure = read_procedure_from_worksheet(wb[sheet])
        else:
            inputs[sheet] = read_inputs_from_worksheet(wb[sheet])

    return {
        "procedure": procedure,
        "inputs": inputs,
        "thermochemical": thermochemical
    }


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

    def process_message(self, connector, host, secret_key, resource, parameters):
        logger = logging.getLogger('__main__')
        experiment = excel_to_json(resource['local_paths'][0])
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
