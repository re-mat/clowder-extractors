import pandas


class ChemDB:
    def __init__(self):
        self.data = None
        self.load_database()

    def load_database(self):
        self.data = pandas.read_csv("https://uofi.box.com/shared/static/p8r6ef1lcj0lk44ggcb6zmv1d66abyfk.csv", index_col="SMILES")

    def exists(self, smiles: str) -> bool:
        return smiles in self.data.index.to_list()

    def density(self, smiles) -> float:
        return self.data.at[smiles, "Density (g/mL)"]

    def molecular_weight(self, smiles) -> float:
        return self.data.at[smiles, "Mwt. (g/mol)"]

    def name(self, smiles: str) -> str:
        return self.data.at[smiles, "Component"]


class ChemistryConverter:
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        self.smiles = smiles
        self.molecular_weight = db.molecular_weight(smiles)
        self.density = db.density(smiles)

        if not mass and not volume:
            raise ValueError("Volume or mass must be specified")

        if mass and volume:
            raise ValueError("Only specify one of mass or volume")

        if mass:
            self.mass = mass
        else:
            self.mass = self.mass_from_volume(volume)

    def mass_from_volume(self, volume: float) -> float:
        return volume * self.density

    def moles(self) -> float:
        return self.mass / self.molecular_weight


class Monomer(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def monomer_mol_percent(self, monomers: list) -> float:
        denominator = sum([monomer.moles() for monomer in monomers])
        return self.moles() / denominator


if __name__ == "__main__":
    c = ChemDB()
    smiles = "C1C=CC2C1C3CC2C=C3"
    print(f"Molecular weight of {c.name(smiles)} is {c.molecular_weight(smiles)}")
    print(f"Density is {c.density(smiles)}")