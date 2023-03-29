#!/usr/bin/env python
from chemistry import Monomer, ChemDB, Catalyst, Inhibitor, Filler, Solvent
import logging

import pyclowder.files
from openpyxl import load_workbook
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage


def compute_values(inputs: dict):
    # First, create lists of input-specific chemistry converters with the observed values
    db = ChemDB()

    db.exists([compound["SMILES"] for compound in inputs['monomers']])
    monomers = {compound["SMILES"]:
        Monomer(compound["SMILES"], db, compound["Measured mass (mg)"],
                 compound["Measured volume (μL)"]) for compound in inputs['monomers']}

    print(monomers)

    db.exists([compound["SMILES"] for compound in inputs['catalysts']])
    catalysts = {compound["SMILES"]:
                     Catalyst(compound["SMILES"], db, compound["Measured mass (mg)"],
                              None) for compound in inputs['catalysts']}
    print(catalysts)

    db.exists([compound["SMILES"] for compound in inputs['inhibitors']])
    inhibitors = {compound["SMILES"]:
                      Inhibitor(compound["SMILES"], db, None,
                                compound["Measured volume (μL)"]) for compound in
                  inputs['inhibitors']
                  }
    print(inhibitors)

    # db.exists([compound["SMILES"] for compound in inputs['additives']])
    # additives = [
    #     [Additive(compound["SMILES"], db, None, compound["Measured volume (μL)"]) for compound in inputs['additives']]
    # ]
    # print(additives)

    # db.exists([compound["SMILES"] for compound in inputs['fillers']])
    # fillers = [
    #     [Filler(compound["SMILES"], db, None, compound["Measured volume (μL)"]) for compound in inputs['fillers']]
    # ]
    # print(fillers)

    db.exists([compound["SMILES"] for compound in inputs['solvents']])
    solvents = {compound["SMILES"]:
                    Solvent(compound["SMILES"], db, compound["Measured mass (mg)"],
                            compound["Measured volume (μL)"]) for compound in
                inputs['solvents']}
    print(solvents)

    # Now compute derived values (which requires knowledge of all of the inputs)
    monomer2 = [{
        "name": monomer["Name"],
        "SMILES": monomer["SMILES"],
        "Measured mass (mg)": monomer["Measured mass (mg)"],
        "Measured volume (μL)": monomer["Measured volume (μL)"],
        "Computed mass (mg)": monomers[monomer["SMILES"]].mass,
        "Molecular Weight": monomers[monomer["SMILES"]].molecular_weight,
        "Moles": monomers[monomer["SMILES"]].moles(),
        "Monomer mol%": monomers[monomer["SMILES"]].monomer_mol_percent(monomers.values())
    }
        for monomer in inputs["monomers"]]
    print("monomer2 --->", monomer2)

    catalyst2 = [{
        "name": catalyst["Name"],
        "SMILES": catalyst["SMILES"],
        "Measured mass (mg)": catalyst["Measured mass (mg)"],
        "Molecular Weight": catalysts[catalyst["SMILES"]].molecular_weight,
        "Moles": catalysts[catalyst["SMILES"]].moles(),
        "Monomer:Catalyst molar ratio": catalysts[catalyst["SMILES"]].catalyst_monomer_molar_ratio(monomers.values())
    }
        for catalyst in inputs["catalysts"]]
    print("catalyst2 --->", catalyst2)

    inhibitor2 = [{
        "name": inhibitor["Name"],
        "SMILES": inhibitor["SMILES"],
        "Measured volume (μL)": inhibitor["Measured volume (μL)"],
        "Density": inhibitors[inhibitor["SMILES"]].density,
        "Computed mass (mg)": inhibitors[inhibitor["SMILES"]].mass,
        "Molecular Weight": inhibitors[inhibitor["SMILES"]].molecular_weight,
        "Moles": inhibitors[inhibitor["SMILES"]].moles(),
        "Inhibitor:Catalyst molar ratio": inhibitors[inhibitor["SMILES"]].inhibitor_catalyst_molar_ratio(list(catalysts.values())[0])
    }
        for inhibitor in inputs["inhibitors"]]
    print("inhibitor2 --->", inhibitor2)


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


def read_batch_id(wb: Workbook) -> str:
    batch_id_range = wb.defined_names["BatchID"].value.split("!")
    batch_id_cell = wb[batch_id_range[0]][batch_id_range[1]]
    return batch_id_cell.value


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
    logger = logging.getLogger('__main__')

    wb = load_workbook(filename=path, data_only=True)
    # Find the data input spreadsheet version
    ss_version = [prop.value for prop
                  in wb.custom_doc_props.props
                  if prop.name == "File Version"][0]

    if ss_version != "1.0":
        logger.error(f"This extractor is not compatible with spreadsheet version {ss_version}")
        return {}

    inputs = {}
    batch_id = read_batch_id(wb)

    for sheet in wb.sheetnames:
        if sheet == "thermochemical":
            thermochemical = read_thermochemical_from_worksheet(wb[sheet])
        elif sheet == "procedure":
            procedure = read_procedure_from_worksheet(wb[sheet])
        else:
            inputs[sheet] = read_inputs_from_worksheet(wb[sheet])

    compute_values(inputs)

    return {
        "Batch ID": batch_id,
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
        logging.getLogger(__name__).debug("default check message : " + str(parameters))
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
    # extractor = ExperimentFromExcel()
    # extractor.start()
    print(excel_to_json("data_entry v2.xlsx"))
