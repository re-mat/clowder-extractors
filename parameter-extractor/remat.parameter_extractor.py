#!/usr/bin/env python
import csv
import logging
import os
import re
import tempfile
from typing import TextIO
import pandas as pd
import matplotlib.pyplot as plt

import pyclowder.files
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage


def make_plot(dsc_file_path, tmpdirname):
    # Plotting Heat Flow vs. Temperature graph
    df = pd.read_csv(dsc_file_path)
    # Reduce the number of columns down to what we need
    df = df.loc[:, ['Temperature', 'Heat Flow']]
    temperature = df['Temperature'].astype(float)
    heat_flow = df['Heat Flow'].astype(float)

    # Plot graph
    plt.plot(temperature, heat_flow)

    # Add axis labels and title
    plt.xlabel("Temperature")
    plt.ylabel("Heat Flow")
    plt.title("Heat Flow vs. Temperature")

    # Save output image files
    plt.tight_layout()
    graph_file_path = os.path.join(tmpdirname, "DSC_Curve.png")
    plt.savefig(graph_file_path, format='png', dpi=300)
    thumb_file_path = os.path.join(tmpdirname, "DSC_Curve_thumb.png")
    plt.savefig(thumb_file_path, format='png', dpi=80)

    plt.close()
    return graph_file_path, thumb_file_path


def extract_baseline_temps(baseline_cursor_x: list[str]) -> (float, float):
        baseline_temps = [float(x.strip().split(' ')[0]) for x in baseline_cursor_x]
        return min(baseline_temps), max(baseline_temps)


def strip_units(param:str) -> float:
    return float(param.strip().split(' ')[0])


def extract_parameters(path: str, dsc_file: TextIO) -> dict:
    section_re = re.compile(r'\[(.*)]$')
    parameters = {}

    stripped_csv = csv.writer(dsc_file)
    heat_flow_column = None
    max_heat_flow = float('-inf')

    with open(path, 'r') as param_file:
        section = None
        header_written = False
        for line in param_file:
            m = section_re.match(line)
            if m:
                section = m.group(1)
                parameters[section] = {}
            else:
                if section != "Step":
                    (key, value) = line.strip("\n").split("\t")
                    if key not in parameters[section]:
                        parameters[section][key] = value
                    else:
                        parameters[section][key] = [parameters[section][key]] + [value]
                else:
                    # This line is part of the DSC output. Copy lines
                    # to the DSC_File.csv file
                    line_values = line.strip("\n").split("\t")

                    # The first column contains the line type
                    line_type = line_values[0]

                    # Remove the first column - it contains the line type
                    line_values = line_values[1:]

                    if line_type == "Variables" and not header_written:
                        # Remember the column number for the heat flow, skipping
                        # the first column (which contained the line type)
                        heat_flow_column = find_heat_flow_column(line_values)

                        # Write the header line
                        stripped_csv.writerow(line_values)

                        # We might see another header in the file. Don't write it out
                        header_written = True

                    elif line_type == "Data point":
                        # See if we have a new max heat flow, but beware of blank lines
                        if heat_flow_column is not None and line_values[heat_flow_column] != "":
                            heat_flow = float(line_values[heat_flow_column])
                            if heat_flow > max_heat_flow:
                                max_heat_flow = heat_flow

                        stripped_csv.writerow(line.strip("\n").split("\t")[1:])

    is_postcure = parameters['Analysis']['Model'] == 'Glass transition'

    min_temp = find_min_temp(parameters["Parameters: Experiment Logs"])
    ramp_rate, max_temp = find_max_temp_and_ramp_rate(parameters['Parameters: Experiment Logs'])
    if is_postcure:
        min_baseline_temp = strip_units(parameters['Analysis']['Onset cursor x'])
        max_baseline_temp = strip_units(parameters['Analysis']['End cursor x'])
        glass_transition_temp = strip_units(parameters['Analysis']['Midpoint'])
        analysis = {
            "Max Heat Flow": round(max_heat_flow, 2),
            "Min Baseline Temp": min_baseline_temp,
            "Max Baseline Temp": max_baseline_temp,
            "Glass transition temperature": glass_transition_temp
        }
    else:
        min_baseline_temp, max_baseline_temp = extract_baseline_temps(parameters['Analysis']['Baseline cursor x'])
        analysis = {
            "Enthalpy (normalized)(J/g)": strip_units(
                parameters['Analysis']['Enthalpy (normalized)']),
            "Peak temperature (°C)": strip_units(
                parameters['Analysis']['Peak temperature']),
            "Onset x (°C)": strip_units(parameters['Analysis']['Onset x']),
            "Max Heat Flow": round(max_heat_flow, 2),
            "Min Baseline Temp": min_baseline_temp,
            "Max Baseline Temp": max_baseline_temp
        }


    experiment = {
        "procedure": {
            "Experiment Type": parameters['Procedure']['Test Name'],
            "Sample Name": parameters['Sample']['Sample Name'],
            "Sample Mass (mg)": parameters['Sample']['Sample Mass'],
            "Reference Pan Type": parameters['Sample']['Pan Type'],
            "Run Date": parameters['Parameters: File Parameters']['Run date'] if 'Run date' in parameters['Parameters: File Parameters'] else parameters['Header']['Run date'],
            "Operator": parameters['Sample']['Operator'],

            'Instrument Name': parameters['Parameters: Configuration']['Instrument Name'],
            'Instrument Type': parameters['Parameters: Configuration']['Instrument Type'],
            'Serial Number': parameters['Parameters: Configuration']['Serial Number'],
            'Location of Instrument': parameters['Parameters: Configuration']['Location of Instrument'],
            'Trios version':  parameters['Parameters: File Parameters']['Trios version'],
            'Ramp rate (°C/min)': ramp_rate,
            'Ramp Min Temp (°C)': min_temp,
            'Ramp Max Temp (°C)': max_temp
        },
        "Analysis": analysis

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

def find_heat_flow_column(line_values: list[str]) -> int:
    heat_flow_column = \
        [i for i, x in enumerate(line_values) if x == "Heat Flow"][0]
    return heat_flow_column


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
        with tempfile.TemporaryDirectory() as tmpdirname:
            dsc_file_path = os.path.join(tmpdirname, "DSC_Curve.csv")
            with open(dsc_file_path, 'w') as dsc_file:
                parameters = extract_parameters(resource['local_paths'][0], dsc_file)

            # Upload the extracted CSV file
            uploaded_id = pyclowder.files.upload_to_dataset(connector, host, secret_key,
                                                            resource['parent'].get('id', None),
                                                            dsc_file_path)

            # Make a plot and thumbnail of the plot
            graph_file_path, thumb_file_path = make_plot(dsc_file_path, tmpdirname)

            # Attach to our uploaded CSV file
            pyclowder.files.upload_preview(connector, host, secret_key, fileid=uploaded_id,
                                           previewfile=graph_file_path, preview_mimetype="image/png")

            pyclowder.files.upload_thumbnail(connector, host, secret_key,
                                             uploaded_id, thumb_file_path)

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
    # with tempfile.TemporaryDirectory() as tmpdirname:
    #     dsc_file_path = os.path.join(tmpdirname, "DSC_Curve.csv")
    #     with open(dsc_file_path, 'w') as dsc_file:
    #         extract_parameters("../LIMS_text_files/772023--Reid-66470-81-3_cure-0.txt", dsc_file)
    #     make_plot(dsc_file_path, tmpdirname)
    #     print(tmpdirname)
    extractor = ParameterExtractor()
    extractor.start()
