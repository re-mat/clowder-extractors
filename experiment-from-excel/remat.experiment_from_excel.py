#!/usr/bin/env python

import hashlib
import logging
import os
import requests
import certifi
import json
import time
from dotenv import load_dotenv
from chemspipy import ChemSpider
from openpyxl.worksheet.worksheet import Worksheet
from pyclowder.extractors import Extractor
from pyclowder.utils import CheckMessage
import pyclowder.files
from openpyxl import load_workbook


def monomore_mol_percent(m_i, M_i, m_i_list, M_i_list):
    denominator = sum([i / j for i, j in zip(m_i_list, M_i_list)])
    numerator = (m_i/M_i)
    return (numerator/denominator)

def volume_of_monomer(m_i_list, rho_i_list):
    return sum([i / j for i, j in zip(m_i_list, rho_i_list)])

def avg_monomer_molecular_weight(X_i_list, M_i_list):
    return sum([i*j for i, j in zip(X_i_list, M_i_list)])

def monomer_catalyst_molar_ratio(m_i_list, M_avg, m_c, M_c):
    numerator = (sum(m_i_list)/M_avg)
    denominator = (m_c/M_c)
    return (numerator/denominator)

def inhibitor_catayst_molar_ratio(V_inh, rho_inh, M_inh, m_c, M_c):
    return ((V_inh*rho_inh)/M_inh)/(m_c/M_c)

def wt_percent_filler(m_fi, m_fi_list, m_i_list, m_c, V_inhrho_inh, V_srho_s):
    return (m_fi/(sum(m_i_list) + sum(m_fi_list) + m_c + (V_inhrho_inh) + (V_srho_s)))

def total_filler_volume(V_fi_list, m_fi_list, rho_fi_list):
    if V_fi_list:
        return sum(V_fi_list) 
    else:
        return sum([i/j for i, j in zip(m_fi_list, rho_fi_list)])

def solvent_concentration(V_s, m_c):
    return V_s/m_c

def total_volume(V_mon, V_inh, V_s, V_f):
    return (V_mon+V_inh+V_s+V_f)

def extra_field_info(path):
    experiment = excel_to_json(path)
    cs = ChemSpider(os.environ.get('chemspider_key'))
    inputs = experiment["inputs"]
    monomers = inputs["monomers"]
    catalysts = inputs["catalysts"]
    inhibitors = inputs["inhibitors"]

    m_c = catalysts[0]['Measured mass (mg)']
    c1 = cs.filter_results(cs.filter_smiles(catalysts[0]['SMILES']))
    if c1:
        c2 = cs.get_compound(c1[0])
        M_c = c2.molecular_weight
    
    V_inh = inhibitors[0]['Measured volume (μL)']
    i1 = cs.filter_results(cs.filter_smiles(inhibitors[0]['SMILES']))
    if i1:
        i2 = cs.get_compound(i1[0])
        M_inh = i2.molecular_weight
        rho_inh = 1

    m_i = []
    V_i = []
    M_i = []
    rho_i = []
    X_i = []
    for i in range(len(monomers)):
        V_i.append(monomers[i]['Measured volume (μL)'])
        m1 = cs.filter_results(cs.filter_smiles(monomers[i]['SMILES']))
        m2 = cs.get_compound(m1[0])
        M_i.append(m2.molecular_weight)
        if monomers[i]['Measured mass (mg)']:
            m_i.append(monomers[i]['Measured mass (mg)'])
        else:
            m_i.append(V_i[i]*rho_i[i]) 
        m_i.append(monomers[i]['Measured mass (mg)'])
        # rho_i.append() 

    for i in range(len(M_i)):
        X_i.append(monomore_mol_percent(m_i[i], M_i[i], m_i, M_i))
        
    V_mon = volume_of_monomer(m_i, rho_i)
    M_avg = avg_monomer_molecular_weight(X_i, M_i)
    m_c_ratio = monomer_catalyst_molar_ratio(m_i, M_avg, m_c, M_c)
    i_c_ratio = inhibitor_catayst_molar_ratio(V_inh, rho_inh, M_inh, m_c, M_c)
    V_inhrho_inh = V_inh*rho_inh
    # V_srho_s = V_sol*rho_sol
    # if m_fi:
    #     wt_filler_per = wt_percent_filler(m_fi, m_i, m_c, V_inhrho_inh, V_srho_s)
    # else:
    #     m_fi = V_fi*rho_fi
    #     wt_filler_per = wt_percent_filler(m_fi, m_i, m_c, V_inhrho_inh, V_srho_s)

    print(X_i)
    # print(V_mon)
    print(M_avg)
    print(m_c_ratio)
    print(i_c_ratio)
    # print(wt_filler_per)


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
    load_dotenv()
    extra_field_info("/Users/sakshitayal/Documents/NCSA_RE-MAT/clowder-extractors/data_entry_v2.xlsx")