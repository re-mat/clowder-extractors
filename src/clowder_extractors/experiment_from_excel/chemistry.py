import math
from enum import Enum

import pandas


class ChemDB:
    def __init__(self):
        self.data = None
        self.load_database()

    def load_database(self):
        # Download the chemistry csv file

        df = pandas.read_csv(
            "https://uofi.box.com/shared/static/p8r6ef1lcj0lk44ggcb6zmv1d66abyfk.csv",
        )

        # Check if the index column is unique
        if df["SMILES"].is_unique:
            # Set the index column
            df.set_index("SMILES", inplace=True)
            self.data = df

        else:
            print("There are duplicate entries in the chemistry database.")
            raise ValueError("There are duplicate entries in the chemistry database.")

    def exists(self, smiles: str | list) -> bool:
        if isinstance(smiles, str):
            return smiles in self.data.index.to_list()
        elif isinstance(smiles, list):
            for test_smiles in smiles:
                if test_smiles and not self.exists(test_smiles):
                    raise ValueError(f"{test_smiles} not in Chemistry Database")
                if test_smiles and (
                    not self.molecular_weight(test_smiles)
                    or pandas.isna(self.molecular_weight(test_smiles))
                ):
                    raise ValueError(
                        f"{test_smiles} does not have a molecular weight in chemistry database"
                    )
            return True

    def density(self, smiles) -> float:
        return self.data.at[smiles, "Density (g/mL)"]

    def molecular_weight(self, smiles) -> float:
        return self.data.at[smiles, "Mwt. (g/mol)"]

    def name(self, smiles: str) -> str:
        return self.data.at[smiles, "Component"]


class ChemistryConverter:
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):

        mass = None if mass == "-" else mass
        volume = None if volume == "-" else volume

        if not mass and not volume:
            raise ValueError("Volume or mass must be specified")

        if not smiles:
            raise ValueError("Smiles field must be specified")

        if mass and volume:
            raise ValueError("Only specify one of mass or volume")

        self.smiles = smiles
        self.molecular_weight = db.molecular_weight(smiles)
        self.density = db.density(smiles)
        self.volume = volume

        if mass:
            self.mass = mass
        else:
            self.mass = self.mass_from_volume(volume)

    def __repr__(self):
        return f"{type(self)} {self.smiles} - Mass: {self.mass}, Volume: {self.volume}, Moles {self.moles()}"

    def mass_from_volume(self, volume: float) -> float:
        if math.isnan(self.density):
            return 0.0
        return volume * self.density

    def moles(self) -> float:
        return self.mass / self.molecular_weight

    def m_volume(self) -> float:
        return self.mass / self.density


class Monomer(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def monomer_mol_percent(self, monomers: list) -> float:
        denominator = sum([monomer.moles() for monomer in monomers])
        monomer_mol_percent = (self.moles() / denominator) * 100.0
        return round(monomer_mol_percent, 2)

    def monomer_volume(self, monomers: list) -> float:
        return sum([monomer.m_volume() for monomer in monomers])

    def average_monomer_molecular_weight(self, monomers: list) -> float:
        M_avg = 0
        for monomer in monomers:
            denominator = sum([monomer.moles() for monomer in monomers])
            X_i = monomer.moles() / denominator
            M_avg += X_i * monomer.molecular_weight
        return M_avg


class Catalyst(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def catalyst_monomer_molar_ratio(self, monomers: list) -> float:
        sum_m_i = sum([monomer.mass for monomer in monomers])
        numerator = sum_m_i / Monomer.average_monomer_molecular_weight(self, monomers)
        catalyst_monomer_molar_ratio = numerator / (self.mass / self.molecular_weight)
        return round(catalyst_monomer_molar_ratio, 2)


class Inhibitor(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def inhibitor_catalyst_molar_ratio(self, catalysts: list[Catalyst]) -> float:
        # iterate through the catalyst list and sum the mass. if mass is None use 0
        catalysts_mass = sum(
            [catalyst.mass if catalyst.mass else 0 for catalyst in catalysts]
        )
        catalysts_molecular_weight = sum(
            [
                catalyst.molecular_weight if catalyst.molecular_weight else 0
                for catalyst in catalysts
            ]
        )
        denominator = catalysts_mass / catalysts_molecular_weight

        inhibitor_mass = 0
        if self.mass:
            inhibitor_mass = self.mass
        elif self.volume and self.density:
            inhibitor_mass = self.volume * self.density

        inhibitor_catalyst_molar_ratio = (
            inhibitor_mass / self.molecular_weight
        ) / denominator
        return round(inhibitor_catalyst_molar_ratio, 2)


class Solvent(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def solvent_concentration(self, catalyst: Catalyst) -> float:
        if self.volume is None:
            if self.mass is None:
                raise ValueError("Solvent Volume or mass must be specified")
            self.volume = self.mass / self.density

        solvent_concentration = self.volume / catalyst.mass
        return round(solvent_concentration, 2)


class Additive(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def additive_weight_percent(
        self, additives: list, monomers: list, catalysts: list, solvents: list
    ) -> float:
        sum_m_i = sum([monomer.mass for monomer in monomers])
        sum_catalysts_mass = sum(
            [catalyst.mass if catalyst.mass else 0 for catalyst in catalysts]
        )
        sum_solvents_mass = sum(
            [
                (
                    solvent.volume * solvent.density
                    if solvent.volume is not None and solvent.density is not None
                    else 0
                )
                for solvent in solvents
            ]
        )

        additive_weight_percent = (
            self.mass
            / (
                sum_m_i
                + sum([additive.mass for additive in additives])
                + sum_catalysts_mass
                + sum_solvents_mass
            )
            * 100.0
        )
        return round(additive_weight_percent, 2)

    def additive_volume_total(self, additives: list) -> float:
        return sum(
            [
                (
                    additive.volume
                    if additive.volume
                    else (additive.mass / additive.density)
                )
                for additive in additives
            ]
        )

    def total_volume(
        self, additives: list, monomers: list, inhibitor: Inhibitor, solvent: Solvent
    ):
        return (
            self.additive_volume_total(additives)
            + Monomer.monomer_volume(self, monomers)
            + inhibitor.volume
            + solvent.volume
        )


class Initiator(ChemistryConverter):
    class InitiatorRole(Enum):
        Catalyst = "Catalyst"
        Solvent = "Solvent"

    def __init__(
        self,
        smiles: str,
        db: ChemDB,
        role: InitiatorRole = None,
        mass=None,
        volume=None,
    ):
        super().__init__(smiles, db, mass, volume)

        # We can assume that if the amount is specified as volume then it is
        # a solvent, otherwise it is a catalyst
        self.role = (
            role
            if role
            else (
                Initiator.InitiatorRole.Solvent
                if volume
                else Initiator.InitiatorRole.Catalyst
            )
        )


if __name__ == "__main__":
    c = ChemDB()
    smiles = "C1C=CC2C1C3CC2C=C3"
    print(f"Molecular weight of {c.name(smiles)} is {c.molecular_weight(smiles)}")
    print(f"Density is {c.density(smiles)}")
