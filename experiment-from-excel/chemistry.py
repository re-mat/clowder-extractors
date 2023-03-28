import pandas
import logging

class ChemDB:
    def __init__(self):
        self.data = None
        self.load_database()

    def load_database(self):
        self.data = pandas.read_csv("https://uofi.box.com/shared/static/p8r6ef1lcj0lk44ggcb6zmv1d66abyfk.csv", index_col="SMILES")

    def exists(self, smiles: str | list) -> bool:
        if type(smiles) == str:
            return smiles in self.data.index.to_list()
        else:
            for test_smiles in smiles:
                if not self.exists(test_smiles):
                    raise ValueError(f"{test_smiles} not in Chemistry Database")

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

        mass = None if mass == "-" else mass
        volume = None if volume == "-" else volume


        if not mass and not volume:
            raise ValueError("Volume or mass must be specified")

        if mass and volume:
            raise ValueError("Only specify one of mass or volume")

        if mass:
            self.mass = mass
        else:
            self.mass = self.mass_from_volume(volume)

    def __repr__(self):
        return f"{type(self)} {self.smiles} - Mass: {self.mass}, Volume: {self.volume()}, Moles {self.moles()}"

    def mass_from_volume(self, volume: float) -> float:
        return volume * self.density

    def moles(self) -> float:
        return self.mass / self.molecular_weight
    
    def volume(self) -> float:
        return self.mass/self.density

class Monomer(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def monomer_mol_percent(self, monomers: list) -> float:
        denominator = sum([monomer.moles() for monomer in monomers])
        return self.moles() / denominator
    
    def monomer_volume(self, monomers: list) -> float:
        return sum([monomer.volume() for monomer in monomers]) 
    
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
        if mass:
            self.m_c = mass
        if volume:
            self.m_V = volume

    def catalyst_monomer_molar_ratio(self, monomers: list, catalyst: list) -> float:
        sum_m_i = sum([monomer.mass for monomer in monomers])
        numerator = sum_m_i / self.average_monomer_molecular_weight(monomers)
        return numerator / (self.m_c / catalyst[0].molecular_weight)

class Inhibitor(Catalyst):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)
        if volume:
            Inhibitor.volume_inh = volume
    
    def inhibitor_catalyst_molar_ratio(self, catalyst: list, inhibitor: list) -> float:
        logger = logging.getLogger('__main__')
        denominator = catalyst[0].mass / catalyst[0].molecular_weight
        logger.info(inhibitor)
        return ((Inhibitor.volume_inh * inhibitor[0].density)/ inhibitor[0].molecular_weight) / denominator

class Solvent(Inhibitor):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)
        if volume:
            Solvent.volume_s = volume

    def solvent_concentration(self, solvent: list, catalyst: list) -> float:
        return Solvent.volume_s / catalyst[0].mass

class Filler(Solvent):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)
        if mass:
            self.m_fi = mass
        if volume:
            Filler.v_f = volume
            self.m_fi = self.mass_from_volume(volume)
    
    def filler_weight_percent(self, filler: list, monomers: list, catalyst: list, inhibitor: list, solvent: list) -> float:
        sum_m_i = sum([monomer.mass for monomer in monomers])
        return ((self.m_fi/sum_m_i) + sum([fill.mass for fill in filler]) + catalyst[0].mass + ( Inhibitor.volume_inh * inhibitor[0].density) + ( Solvent.volume_s * solvent[0].density))

    def filler_volume_total(self, filler: list) -> float: 
        if self.mass:
            return sum([(fill.mass/fill.density) for fill in filler])
        else:
            return sum([fill.volume for fill in filler])

    def total_volume(self, monomers: list, inhibitor: list, solvent: list, filler: list):
        return Filler.v_f + self.monomer_volume(monomers) + Inhibitor.volume_inh + Solvent.volume_s


if __name__ == "__main__":
    c = ChemDB()
    smiles = "C1C=CC2C1C3CC2C=C3"
    print(f"Molecular weight of {c.name(smiles)} is {c.molecular_weight(smiles)}")
    print(f"Density is {c.density(smiles)}")