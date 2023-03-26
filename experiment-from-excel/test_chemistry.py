import math

import pytest
from _pytest.fixtures import fixture

from chemistry import ChemDB, ChemistryConverter, Monomer

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


