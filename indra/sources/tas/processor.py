from __future__ import absolute_import, print_function, unicode_literals
from builtins import dict, str

__all__ = ['TasProcessor']

from indra.statements import Inhibition, Agent, Evidence
from indra.databases.lincs_client import LincsClient
from indra.databases.hgnc_client import get_hgnc_from_entrez


CLASS_MAP = {'1': 'Kd < 100nM', '2': '100nM < Kd < 1uM', '3': '1uM < Kd < 10uM',
             '10': 'Kd > 10uM'}


class TasProcessor(object):
    """A processor for Target Affinity Spectrum data compiled by N. Moret.

    This data was compiled in the HMS LSP as an improvement on the "arbitrary"
    selection of targets present in the similar LINCS dataset.
    """
    def __init__(self, data, affinity_class_limit):
        self._data = data
        self._lc = LincsClient()
        self.affinity_class_limit = affinity_class_limit

        self.statements = []
        for row in data:
            # Skip rows that are above the affinity class limit
            if int(row['class_min']) > affinity_class_limit:
                continue
            self._process_row(row)
        return

    def _process_row(self, row):
        drug = self._extract_drug(row['hms_id'])
        prot = self._extract_protein(row['approved_symbol'], row['gene_id'])
        ev = self._make_evidence(row['class_min'])
        self.statements.append(Inhibition(drug, prot, evidence=ev))
        return

    def _extract_drug(self, hms_id):
        refs = self._lc.get_small_molecule_ref(hms_id,
                                               id_type='short-hms-lincs')
        name = self._lc.get_small_molecule_name(hms_id,
                                                id_type='short-hms-lincs')
        return Agent(name, db_refs=refs)

    def _extract_protein(self, name, gene_id):
        hgnc_id = get_hgnc_from_entrez(gene_id)
        refs = self._lc.get_protein_ref(gene_id, id_type='entrez')
        if hgnc_id is not None:
            refs['HGNC'] = hgnc_id
        return Agent(name, db_refs=refs)

    def _make_evidence(self, class_min):
        ev = Evidence(source_api='tas', epistemics={'direct': True},
                      annotations={'class_min': CLASS_MAP[class_min]})
        return ev
