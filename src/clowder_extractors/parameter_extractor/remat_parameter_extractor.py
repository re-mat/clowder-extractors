#!/usr/bin/env python
import copy
import csv
import logging
import os
import re
import sys
import tempfile
from logging import Logger
from typing import TextIO
import pandas as pd
import matplotlib.pyplot as plt
import requests

import pyclowder.files
import pyclowder.datasets
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import json


# from clowder_extractors.experiment_from_excel.remat_experiment_from_excel import compute_values
from clowder_extractors.experiment_from_excel.remat_experiment_from_excel import (
    excel_to_json,
)
from clowder_extractors.parameter_extractor.notes import Notes

# sample datasheets locations
url_mapping = {
    "CureKin_IA": "https://uofi.box.com/shared/static/12t8k0siycj2ec82sb9mrxnlnbt0ggq7",
    "PostCure_IA": "https://uofi.box.com/shared/static/5vb0ek7htxk2wpoklyxsvk1ctgjwi9kw",
    "CureKin_LDM": "https://uofi.box.com/shared/static/k0ix1qjmle4iv5trvxqodbmaa8ip2roh",
}
datasheet_folder = "https://uofi.box.com/shared/static/91pz5we1ywgz7iftail1c0bulfgriq2o"


def make_plot(dsc_file_path, tmpdirname):
    # Plotting Heat Flow vs. Temperature graph
    df = pd.read_csv(dsc_file_path)
    # Reduce the number of columns down to what we need
    df = df.loc[:, ["Temperature", "Heat Flow"]]
    temperature = df["Temperature"].astype(float)
    heat_flow = df["Heat Flow"].astype(float)

    # Plot graph
    plt.plot(temperature, heat_flow)

    # Add axis labels and title
    plt.xlabel("Temperature")
    plt.ylabel("Heat Flow")
    plt.title("Heat Flow vs. Temperature")

    # Save output image files
    plt.tight_layout()
    graph_file_path = os.path.join(tmpdirname, "DSC_Curve.png")
    plt.savefig(graph_file_path, format="png", dpi=300)
    thumb_file_path = os.path.join(tmpdirname, "DSC_Curve_thumb.png")
    plt.savefig(thumb_file_path, format="png", dpi=80)

    plt.close()
    return graph_file_path, thumb_file_path


def extract_baseline_temps(baseline_cursor_x: list[str]) -> (float, float):
    baseline_temps = [float(x.strip().split(" ")[0]) for x in baseline_cursor_x]
    return min(baseline_temps), max(baseline_temps)


def strip_units(param: str) -> float:
    return float(param.strip().split(" ")[0])


def extract_parameters(
    path: str, dsc_file: TextIO, logger: Logger, temp_dir: str
) -> (dict, str):
    section_re = re.compile(r"\[(.*)]$")
    parameters = {}

    stripped_csv = csv.writer(dsc_file)
    heat_flow_column = None
    max_heat_flow = float("-inf")

    with open(path, "r") as param_file:
        section = None
        header_written = False
        for line in param_file:
            m = section_re.match(line)
            if m:
                section = m.group(1)
                parameters[section] = {}
            else:
                if section != "Step":
                    line_value = line.strip("\n").split("\t")
                    if len(line_value) == 2:
                        (key, value) = line.strip("\n").split("\t")
                        if key not in parameters[section]:
                            parameters[section][key] = value
                        else:
                            parameters[section][key] = [parameters[section][key]] + [
                                value
                            ]
                    # Special case for the Project line
                    elif len(line_value) == 1 and line_value[0] == "Project":
                        parameters[section]["Project"] = " ".join(line_value)

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
                        if (
                            heat_flow_column is not None
                            and line_values[heat_flow_column] != ""
                        ):
                            heat_flow = float(line_values[heat_flow_column])
                            if heat_flow > max_heat_flow:
                                max_heat_flow = heat_flow

                        stripped_csv.writerow(line.strip("\n").split("\t")[1:])

    is_postcure = parameters["Analysis"]["Model"] == "Glass transition"

    min_temp = find_min_temp(parameters["Parameters: Experiment Logs"])
    ramp_rate, max_temp = find_max_temp_and_ramp_rate(
        parameters["Parameters: Experiment Logs"]
    )
    if is_postcure:
        min_baseline_temp = strip_units(parameters["Analysis"]["Onset cursor x"])
        max_baseline_temp = strip_units(parameters["Analysis"]["End cursor x"])
        glass_transition_temp = strip_units(parameters["Analysis"]["Midpoint"])
        analysis = {
            "Max Heat Flow": round(max_heat_flow, 2),
            "Min Baseline Temp": min_baseline_temp,
            "Max Baseline Temp": max_baseline_temp,
            "Glass transition temperature": glass_transition_temp,
        }
    else:
        min_baseline_temp, max_baseline_temp = extract_baseline_temps(
            parameters["Analysis"]["Baseline cursor x"]
        )
        analysis = {
            "Enthalpy (normalized)(J/g)": strip_units(
                parameters["Analysis"]["Enthalpy (normalized)"]
            ),
            "Peak temperature (°C)": strip_units(
                parameters["Analysis"]["Peak temperature"]
            ),
            "Onset x (°C)": strip_units(parameters["Analysis"]["Onset x"]),
            "Max Heat Flow": round(max_heat_flow, 2),
            "Min Baseline Temp": min_baseline_temp,
            "Max Baseline Temp": max_baseline_temp,
        }

    trios_notes = Notes(parameters)
    # "CureKin_IA", "PostCure_IA", "CureKin_LDM"
    template_datasheet = trios_notes.notes["Data_sheet"]
    # IA, LDM, etc
    initials = template_datasheet.split("_")[1]

    # Download the datasheet file for the given space
    pd, datasheet_file = read_data_sheet_file(
        url_mapping[template_datasheet], template_datasheet + ".xlsx", temp_dir
    )
    trios_notes.path = datasheet_file

    if not trios_notes.notes:
        logger.debug("No notes found in the TRIOS file")

    experiment = {
        "procedure": {
            "Experiment Type": parameters["Procedure"]["Test Name"],
            "Sample Name": parameters["Sample"]["Sample Name"],
            "Sample Mass (mg)": parameters["Sample"]["Sample Mass"],
            "Reference Pan Type": parameters["Sample"]["Pan Type"],
            "Run Date": (
                parameters["Parameters: File Parameters"]["Run date"]
                if "Run date" in parameters["Parameters: File Parameters"]
                else parameters["Header"]["Run date"]
            ),
            "Operator": parameters["Sample"]["Operator"],
            "Instrument Name": parameters["Parameters: Configuration"][
                "Instrument Name"
            ],
            "Instrument Type": parameters["Parameters: Configuration"][
                "Instrument Type"
            ],
            "Serial Number": parameters["Parameters: Configuration"]["Serial Number"],
            "Location of Instrument": parameters["Parameters: Configuration"][
                "Location of Instrument"
            ],
            "Trios version": parameters["Parameters: File Parameters"]["Trios version"],
            "Ramp rate (°C/min)": ramp_rate,
            "Ramp Min Temp (°C)": min_temp,
            "Ramp Max Temp (°C)": max_temp,
        },
        "Analysis": analysis,
    }
    # Make a deep copy of the experiment dict to use for the inputs
    # Original experiment will be uploaded in parameter extractor and new copy will be modified to be used by excel extractor
    experiment_to_upload = copy.deepcopy(experiment)

    # Add the inputs object and Batch ID from experiment_from_excel to the experiment object
    try:
        result_from_excel = excel_to_json(datasheet_file)
        if result_from_excel is None:
            logger.debug("Error: result_from_excel is None")
        elif "inputs" not in result_from_excel:
            logger.debug("Error: 'inputs' field is missing in result_from_excel")
        else:
            experiment["inputs"] = result_from_excel["inputs"]

            if "Batch ID" in result_from_excel:
                experiment["Batch ID"] = result_from_excel["Batch ID"]
            # Append Excel extractor procedure to the experiment procedure
            # Remove below block if needed to decouple both extractors
            if "procedure" in result_from_excel:
                for key, value in result_from_excel["procedure"].items():
                    if key not in experiment["procedure"]:
                        experiment["procedure"][key] = value
                    else:
                        # Handle the case where the key already exists
                        if isinstance(experiment["procedure"][key], list):
                            experiment["procedure"][key].append(value)
                        else:
                            experiment["procedure"][key] = [
                                experiment["procedure"][key],
                                value,
                            ]
                experiment["procedure"]["Mix Date and Time"] = str(
                    trios_notes.notes.get("Mix Date and time", None)
                )

            trios_notes.map_input_values_from_notes_to_experiment(experiment, initials)
        logger.info("Datasheet to be uploaded is %s", datasheet_file)
    except Exception as e:
        logger.error("Error processing excel file:  %s", e, exc_info=True)

    print(json.dumps(experiment_to_upload, indent=4, default=str, ensure_ascii=False))
    logger.info(
        "Experiment json: %s",
        json.dumps(experiment, indent=4, default=str, ensure_ascii=False),
    )
    return experiment_to_upload, datasheet_file


def find_min_temp(log_entries: dict) -> float:
    # Find the Equilibrate log entry
    min_temp_re = re.compile(r"Equilibrate Segment ([-+]?\d+) \(C\) Started$")

    equilibrate_segment = next(
        filter(lambda log_entry: min_temp_re.match(log_entry), log_entries.values())
    )
    match = min_temp_re.match(equilibrate_segment)
    return float(match.group(1)) if match else float("NaN")


def find_max_temp_and_ramp_rate(log_entries: dict) -> (float, float):
    # Find the Ramp Segment log entry
    ramp_rate_and_temp_re = re.compile(
        r"Ramp Segment (\d*\.*\d+) C/min to ([-+]?(?:\d*\.*\d+)) Started"
    )

    equilibrate_segment = next(
        filter(
            lambda log_entry: ramp_rate_and_temp_re.match(log_entry),
            log_entries.values(),
        )
    )
    match = ramp_rate_and_temp_re.match(equilibrate_segment)

    return float(match.group(1)), (
        float(match.group(2)) if match else (float("NaN"), float("NaN"))
    )


def find_heat_flow_column(line_values: list[str]) -> int:
    heat_flow_column = [i for i, x in enumerate(line_values) if x == "Heat Flow"][0]
    return heat_flow_column


def extract_notes_field(parameters: dict) -> dict:
    parsed_dict = {}
    if "Sample" in parameters and "Notes" in parameters["Sample"]:
        notes = parameters["Sample"]["Notes"]
        pairs = notes.split(";")
        for pair in pairs:
            if ":" in pair:
                key, val = pair.split(":", 1)
                parsed_dict[key.strip()] = val.strip()
    return parsed_dict


def read_data_sheet_file(
    file_path: str, file_name: str, temp_dir: str
) -> (pd.DataFrame, str):

    try:
        # Send a GET request to the URL
        response = requests.get(file_path, stream=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses

        # Extract the filename from the Content-Disposition header
        if "Content-Disposition" in response.headers:
            content_disposition = response.headers["Content-Disposition"]
            filename = re.findall('filename="(.+)"', content_disposition)
            if filename:
                output_file = filename[0]
            else:
                output_file = file_name
        else:
            output_file = file_name

        # Use provided temp directory
        temp_file_path = os.path.join(temp_dir, output_file)

        # Write the content to a local file
        with open(temp_file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"File downloaded successfully as {output_file}")

        # Read the downloaded file into a pandas DataFrame
        df = pd.read_excel(temp_file_path)

        return df, temp_file_path

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while downloading the file: {e}")
        return None, None


class ParameterExtractor(Extractor):
    def __init__(self):
        Extractor.__init__(self)

        # parse command line and load default logging configuration
        self.setup()

        # setup logging for the extractor
        logging.getLogger("pyclowder").setLevel(logging.DEBUG)
        logging.getLogger("__main__").setLevel(logging.DEBUG)

    def check_message(self, connector, host, secret_key, resource, parameters):
        return CheckMessage.download

    def process_message(self, connector, host, secret_key, resource, parameters):
        logger = logging.getLogger("__main__")
        with tempfile.TemporaryDirectory() as tmpdirname:
            dsc_file_path = os.path.join(tmpdirname, "DSC_Curve.csv")
            with open(dsc_file_path, "w") as dsc_file:
                parameters, datasheet_file = extract_parameters(
                    resource["local_paths"][0], dsc_file, logger, tmpdirname
                )
            # Upload datasheet from temp directory
            temp_datasheet_path = os.path.join(tmpdirname, datasheet_file)

            # Upload the extracted CSV file
            dataset_id = resource["parent"].get("id", None)
            uploaded_id = pyclowder.files.upload_to_dataset(
                connector,
                host,
                secret_key,
                dataset_id,
                dsc_file_path,
            )

            # Make a plot and thumbnail of the plot
            graph_file_path, thumb_file_path = make_plot(dsc_file_path, tmpdirname)

            # Attach to our uploaded CSV file
            pyclowder.files.upload_preview(
                connector,
                host,
                secret_key,
                fileid=uploaded_id,
                previewfile=graph_file_path,
                preview_mimetype="image/png",
            )

            pyclowder.files.upload_thumbnail(
                connector, host, secret_key, uploaded_id, thumb_file_path
            )
            logger.info("uploading datasheet file to dataset %s", datasheet_file)

            # Uploaded the downloaded datasheet file to the dataset
            pyclowder.files.upload_to_dataset(
                connector, host, secret_key, dataset_id, temp_datasheet_path, False
            )

        logger.debug(parameters)

        # store results as metadata
        metadata = {
            "@context": ["https://clowder.ncsa.illinois.edu/contexts/metadata.jsonld"],
            "dataset_id": resource["parent"].get("id", None),
            "content": parameters,
            "agent": {
                "@type": "cat:extractor",
                "extractor_id": host + "api/extractors/" + self.extractor_info["name"],
            },
        }
        # Add extractor metadata to dataset
        try:
            pyclowder.datasets.upload_metadata(
                connector,
                host,
                secret_key,
                resource["parent"].get("id", None),
                metadata,
            )
        except Exception as e:
            logger.error("Error uploading metadata: %s", e, exc_info=True)


def main():
    if len(sys.argv) > 1:
        logger = logging.getLogger("__main__")
        with tempfile.TemporaryDirectory() as tmpdirname:
            dsc_file_path = os.path.join(tmpdirname, "DSC_Curve.csv")
            with open(dsc_file_path, "w") as dsc_file:
                extract_parameters(sys.argv[1], dsc_file, logger, tmpdirname)
            make_plot(dsc_file_path, tmpdirname)
            # find_volume_column()
            print(tmpdirname)
    else:
        extractor = ParameterExtractor()
        extractor.start()


if __name__ == "__main__":
    main()
