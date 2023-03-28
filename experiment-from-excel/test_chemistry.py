import math

import pytest
from _pytest.fixtures import fixture

from chemistry import ChemDB, ChemistryConverter, Monomer, Catalyst, Inhibitor, Filler, Solvent

dicyclopentadiene = "C1C=CC2C1C3CC2C=C3"
enb = "CC=C1CC2CC1C=C2"
cached_db = ChemDB()


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


def test_moles(db):
    converter = ChemistryConverter(dicyclopentadiene, db, volume=887.0)
    assert round(converter.moles(), 2) == 6.58


def test_monomer(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]

    assert round(monomers[0].monomer_mol_percent(monomers), 2) == 0.59
    assert round(monomers[0].monomer_volume(monomers), 2) == 1514.85
    assert round(monomers[0].average_monomer_molecular_weight(monomers), 2) == 127.23

def test_monomer_catalyst(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    catalyst = [
        Catalyst(dicyclopentadiene, db, mass=870.0)
    ]

    assert round(catalyst[0].catalyst_monomer_molar_ratio(monomers,catalyst), 2) == 1.71


def test_catalyst_inhibitor(db):
    inhibitor = [
        Inhibitor(enb, db, volume=887.0)   
    ]
    catalyst = [
        Catalyst(dicyclopentadiene, db, mass=870.0)
    ]

    assert round(inhibitor[0].inhibitor_catalyst_molar_ratio(catalyst,inhibitor), 2) == 1.0 

def test_fillers(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = [
        Inhibitor(enb, db, volume=887.0)   
    ]
    catalyst = [
        Catalyst(dicyclopentadiene, db, mass=870.0)
    ]
    filler = [
        Filler(dicyclopentadiene, db, mass=870.0),
        Filler(enb, db, mass=560.0)
    ]
    solvent = [
        Solvent(enb, db, volume=887.0)   
    ]

    assert round(filler[0].filler_weight_percent(filler, monomers, catalyst, inhibitor, solvent), 2) == 3884.79
    assert round(filler[0].filler_volume_total(filler), 2) == 1514.85

def test_fillers_converter_volume(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = [
        Inhibitor(enb, db, volume=887.0)   
    ]
    catalyst = [
        Catalyst(dicyclopentadiene, db, mass=870.0)
    ]
    filler = [
        Filler(enb, db, volume=560.0),
        Filler(dicyclopentadiene, db, volume=870.0),
       
    ]
    solvent = [
        Solvent(enb, db, volume=887.0)   
    ]

    assert round(filler[0].filler_weight_percent(filler, monomers, catalyst, inhibitor, solvent), 2) == 3807.21
    assert round(filler[0].filler_volume_total(filler), 2) == 1430.0

def test_solvent_volume(db):
    solvent = [
        Solvent(enb, db, volume=887.0)   
    ]
    catalyst = [
        Catalyst(dicyclopentadiene, db, mass=870.0)
    ]

    assert round(solvent[0].solvent_concentration(solvent,catalyst), 2) == 1.02


def test_total_volume(db):
    monomers = [
        Monomer(dicyclopentadiene, db, mass=870.0),
        Monomer(enb, db, mass=560.0)
    ]
    inhibitor = [
        Inhibitor(enb, db, volume=887.0)   
    ]
    solvent = [
        Solvent(enb, db, volume=887.0)   
    ]
    filler = [
        Filler(enb, db, volume=560.0),
        Filler(dicyclopentadiene, db, volume=870.0),
       
    ]

    assert round(filler[0].total_volume(monomers, inhibitor, solvent, filler), 2) == 4124.85