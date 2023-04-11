import pandas

class ChemDB:
    def __init__(self):
        self.data = None
        self.load_database()

    def load_database(self):
        self.data = pandas.read_csv("https://uofi.box.com/shared/static/p8r6ef1lcj0lk44ggcb6zmv1d66abyfk.csv", index_col="SMILES")

    def exists(self, smiles: str | list) -> bool:
        if type(smiles) == str:
            return smiles in self.data.index.to_list()
        elif type(smiles) == list:
            for test_smiles in smiles:
                if test_smiles and not self.exists(test_smiles):
                    raise ValueError(f"{test_smiles} not in Chemistry Database")
                if test_smiles and \
                    (not self.molecular_weight(test_smiles) or pandas.isna(self.molecular_weight(test_smiles))):
                        raise  ValueError(f"{test_smiles} does not have a molecular weight in chemistry database")
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
        return volume * self.density

    def moles(self) -> float:
        return self.mass / self.molecular_weight
    
    def m_volume(self) -> float:
        return self.mass/self.density

class Monomer(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def monomer_mol_percent(self, monomers: list) -> float:
        denominator = sum([monomer.moles() for monomer in monomers])
        return (self.moles() / denominator) * 100.0
    
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
        return numerator / (self.mass / self.molecular_weight)

class Inhibitor(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)
    
    def inhibitor_catalyst_molar_ratio(self, catalyst: Catalyst) -> float:
        denominator = catalyst.mass / catalyst.molecular_weight
        return ((self.volume * self.density)/ self.molecular_weight) / denominator

class Solvent(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def solvent_concentration(self, catalyst: Catalyst) -> float:
        return self.volume / catalyst.mass
class Additive(ChemistryConverter):
    def __init__(self, smiles: str, db: ChemDB, mass=None, volume=None):
        super().__init__(smiles, db, mass, volume)

    def additive_weight_percent(self, additives: list, monomers: list, catalyst: Catalyst, solvent: Solvent) -> float:
        sum_m_i = sum([monomer.mass for monomer in monomers])
        return self.mass/(sum_m_i + sum([additive.mass for additive in additives]) + catalyst.mass + ( solvent.volume * solvent.density)) * 100.0
    
    def additive_volume_total(self, additives: list) -> float: 
        return sum([additive.volume if additive.volume else (additive.mass/additive.density) for additive in additives])

    def total_volume(self, additives: list, monomers: list, inhibitor: Inhibitor, solvent: Solvent):
        return self.additive_volume_total(additives) + Monomer.monomer_volume(self, monomers) + inhibitor.volume + solvent.volume

if __name__ == "__main__":
    c = ChemDB()
    smiles = "C1C=CC2C1C3CC2C=C3"
    print(f"Molecular weight of {c.name(smiles)} is {c.molecular_weight(smiles)}")
    print(f"Density is {c.density(smiles)}")