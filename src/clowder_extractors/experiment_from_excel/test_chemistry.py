import math

import pytest
from _pytest.fixtures import fixture

from chemistry import ChemDB, ChemistryConverter, Monomer, Catalyst, Inhibitor, Additive, Solvent

dicyclopentadiene = "C1C=CC2C1C3CC2C=C3"
enb = "CC=C1CC2CC1C=C2"
cached_db = ChemDB()
dhf = "C1COC=C1"
gc2 = "CC1=CC(=C(C(=C1)C)N2CCN(C2=[Ru](=CC3=CC=CC=C3)(Cl)Cl)C4=C(C=C(C=C4C)C)C)C.C1CCC(CC1)P(C2CCCCC2)C3CCCCC3"
mn1 = "CC1=CC=CC2=CC=CC=C12"
fumed_si = "O=[Si]=O"
pbd = "C{-}C=CC{n+}"

@fixture
def db():
    return cached_db


def test_chem_db(db):
    assert db.exists(dicyclopentadiene)
    assert not db.exists("Phlogiston")


def test_density(db):
    assert db.density(dicyclopentadiene) == 0.98


def test_molecular_weight(db):
    assert db.molecular_weight(dicyclopentadiene) == 132.2


def test_converter_mass(db):
    converter = ChemistryConverter(dicyclopentadiene, db, mass=870.0)
    assert converter.mass == 870.0


def test_converter_volume(db):
    converter = ChemistryConverter(dicyclopentadiene, db, volume=887.0)
    assert converter.mass == 869.26


def test_converter_bad_values(db):
    with pytest.raises(ValueError):
        ChemistryConverter(dicyclopentadiene, db, volume=None, mass=None)

    with pytest.raises(ValueError):
        ChemistryConverter(dicyclopentadiene, db, volume=100, mass=200)

    with pytest.raises(ValueError) as excinfo:
        db = ChemDB()
        ChemistryConverter("", db, mass=10, volume=None)
    assert str(excinfo.value) == "Smiles field must be specified"


def test_moles(db):
    converter = ChemistryConverter(dicyclopentadiene, db, volume=887.0)
    assert round(converter.moles(), 2) == 6.58


def test_monomer(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]

    assert monomers[0].monomer_mol_percent(monomers) == 58.55
    assert round(monomers[0].monomer_volume(monomers), 2) == 1514.85
    assert round(monomers[0].average_monomer_molecular_weight(monomers), 2) == 127.23

def test_monomer_catalyst(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    catalyst = Catalyst(dicyclopentadiene, db, mass=870.0)

    assert catalyst.catalyst_monomer_molar_ratio(monomers) == 1.71


def test_catalyst_inhibitor(db):
    inhibitor = Inhibitor(enb, db, volume=887.0)   
    catalyst = Catalyst(dicyclopentadiene, db, mass=870.0)

    assert inhibitor.inhibitor_catalyst_molar_ratio(catalyst) == 1.0 

def test_additives(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = Inhibitor(enb, db, volume=887.0)   
    catalyst = Catalyst(dicyclopentadiene, db, mass=870.0)
    additives = [
        Additive(dicyclopentadiene, db, mass=870.0),
        Additive(enb, db, mass=560.0)
    ]
    solvent = Solvent(enb, db, volume=887.0)   

    assert additives[0].additive_weight_percent(additives, monomers, catalyst, inhibitor, solvent) == 3884.79
    assert round(additives[0].additive_volume_total(additives), 2) == 1514.85

def test_additives_converter(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = Inhibitor(enb, db, volume=887.0)   
    catalyst = Catalyst(dicyclopentadiene, db, mass=870.0)
    additives = [
        Additive(enb, db, volume=560.0),
        Additive(dicyclopentadiene, db, volume=870.0),
       
    ]
    solvent = Solvent(enb, db, volume=887.0)   

    assert additives[0].additive_weight_percent(additives, monomers, catalyst, solvent) == 11.25
    
def test_filler_volume(db):
    additives = [
        Additive(enb, db, volume=560.0),
        Additive(dicyclopentadiene, db, volume=870.0),
       
    ]
    assert round(additives[0].additive_volume_total(additives), 2) == 1430.0

def test_filler_volume_converter(db):
    additives = [
        Additive(enb, db, mass=560.0),
        Additive(dicyclopentadiene, db, mass=870.0),
       
    ]
    assert round(additives[0].additive_volume_total(additives), 2) == 1514.85

def test_filler_mass_volume_combination(db):
    additives = [
        Additive(enb, db, mass=560.0),
        Additive(dicyclopentadiene, db, volume=870.0),
       
    ]
    assert round(additives[0].additive_volume_total(additives), 2) == 1497.1

def test_solvent_volume(db):
    solvent =  Solvent(enb, db, volume=887.0)   
    catalyst = Catalyst(dicyclopentadiene, db, mass=870.0)

    assert solvent.solvent_concentration(catalyst) == 1.02


def test_total_volume(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = Inhibitor(enb, db, volume=887.0)   
    solvent = Solvent(enb, db, volume=887.0)   
    additives = [
        Additive(enb, db, volume=560.0),
        Additive(dicyclopentadiene, db, volume=870.0)
    ]

    assert round(additives[0].total_volume(additives, monomers, inhibitor, solvent), 2) == 4718.85


def test_additives(db):
    a = Additive(dicyclopentadiene, db, mass=870.0)
    assert a

def test_derived_values(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=10.51),
        Monomer(enb, db, mass=0.55)
    ]
    catalyst = Catalyst(gc2, db, mass=7.14/1000)
    solvent = Solvent(mn1, db, volume=357.87)  
    additives = [
        Additive(fumed_si, db, mass=0.59),
        Additive(pbd, db, mass=0.12)
    ]

    assert monomers[0].monomer_mol_percent(monomers) == 94.56
    assert monomers[1].monomer_mol_percent(monomers) == 5.44
    assert catalyst.catalyst_monomer_molar_ratio(monomers) == 9997.09
    # assert round(solvent.solvent_concentration(catalyst), 2) == 0.02
    assert additives[1].additive_weight_percent(additives, monomers, catalyst, solvent) == 0.03