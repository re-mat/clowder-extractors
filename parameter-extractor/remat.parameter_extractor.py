#!/usr/bin/env python

import logging
import os
import re

import pyclowder.files
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage


def extract_parameters(path:str) -> dict:
    section_re = re.compile(r'\[(.*)\]$')
    parameters = {}

    with open(path, 'r') as param_file:
        section = None
        for line in param_file:
            m = section_re.match(line)
            if m:
                section = m.group(1)
                parameters[section] = {}
            else:
                (key, value) = line.strip("\n").split("\t")
                parameters[section][key] = value

    min_temp = find_min_temp(parameters["Experiment Logs"])
    ramp_rate, max_temp = find_max_temp_and_ramp_rate(parameters['Experiment Logs'])

    experiment = {
        "procedure": {
            "Experiment Type": parameters['Procedure']['Procedure Name'],
            "Sample Name": parameters['Procedure']['Sample Name'],
            "Sample Mass (mg)": parameters['Procedure']['Sample Mass'],
            "Reference Pan Type": parameters['Procedure']['Pan Type'],
            "Run Date": parameters['File Parameters']['Run date'],
            "Operator": parameters['Procedure']['Operator'],

            'Instrument Name': parameters['Configuration']['Instrument Name'],
            'Instrument Type': parameters['Configuration']['Instrument Type'],
            'Serial Number': parameters['Configuration']['Serial Number'],
            'Location of Instrument': parameters['Configuration']['Location of Instrument'],
            'Trios version':  parameters['File Parameters']['Trios version'],
            'Ramp rate (°C/min)': ramp_rate,
            'Temp range (°C)': f"{min_temp}-{max_temp}"
        }
    }
    return experiment


def find_min_temp(log_entries: dict) -> float:
    # Find the Equilibrate log entry
    min_temp_re = re.compile(r'Equilibrate Segment (\d+) \(C\) Started$')

    equilibrate_segment = next(
        filter(lambda log_entry: min_temp_re.match(log_entry),
               log_entries.values()))
    match = min_temp_re.match(equilibrate_segment)
    return float(match.group(1)) if match else float("NaN")


def find_max_temp_and_ramp_rate(log_entries: dict) -> (float, float):
    # Find the Ramp Segment log entry
    ramp_rate_and_temp_re = re.compile(r'Ramp Segment (\d*\.*\d+) C/min to ([-+]?(?:\d*\.*\d+)) Started')

    equilibrate_segment = next(
        filter(lambda log_entry: ramp_rate_and_temp_re.match(log_entry),
               log_entries.values()))
    match = ramp_rate_and_temp_re.match(equilibrate_segment)

    return float(match.group(1)), float(match.group(2)) if match else (float("NaN"), float("NaN"))


class ParameterExtractor(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the extractor
        logging.getLogger('pyclowder').setLevel(logging.DEBUG)
        logging.getLogger('__main__').setLevel(logging.DEBUG)

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.download

    def process_message(self, connector, host, secret_key, resource, parameters):
        logger = logging.getLogger('__main__')
        parameters = extract_parameters(resource['local_paths'][0])
        logger.debug(parameters)

        # store results as metadata
        metadata = {
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "dataset_id": resource['parent'].get('id', None),
            "content": parameters,
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "api/extractors/" + self.extractor_info['name']
            }
        }

        pyclowder.datasets.upload_metadata(connector, host, secret_key,
                                           resource['parent'].get('id', None), metadata)


if __name__ == "__main__":
    extractor = ParameterExtractor()
    extractor.start()
