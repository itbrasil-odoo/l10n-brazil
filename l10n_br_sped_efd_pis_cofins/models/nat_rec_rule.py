# Copyright 2026 - TODAY, KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo import api, fields, models

# Tabela da natureza da receita de cada CST sem contribuição (Guia 1.35,
# Registro M410, campo 02).
NAT_REC_TABLES = [
    ("04", "04 - Monofásica, revenda a alíquota zero (tabelas 4.3.10/4.3.11)"),
    ("05", "05 - Substituição tributária (tabela 4.3.12)"),
    ("06", "06 - Alíquota zero (tabela 4.3.13)"),
    ("07", "07 - Isenção (tabela 4.3.14)"),
    ("08", "08 - Sem incidência (tabela 4.3.15)"),
    ("09", "09 - Suspensão (tabela 4.3.16)"),
]


class EfdPisCofinsNatRecRule(models.Model):
    """Natureza da receita (M410/M810) que não sai do NCM.

    As tabelas 4.3.10 a 4.3.16 dão a natureza pelo NCM só em parte. A maior
    parte da 4.3.15 (sem incidência) e da 4.3.14 (isenção) depende do
    enquadramento legal da operação, que é decisão do contador: a regra
    guarda essa decisão por CST e, se for o caso, por prefixo de NCM.
    """

    # fora do prefixo "l10n_br_sped.efd_pis_cofins": o sped_base trata todo
    # modelo com esse prefixo como registro do leiaute
    _name = "l10n_br_sped_efd_pis_cofins.nat_rec.rule"
    _description = "EFD-Contribuições: natureza da receita por CST e NCM"
    _order = "cst, ncm_prefix desc"

    company_id = fields.Many2one(
        comodel_name="res.company",
        help="Vazio vale para todas as empresas.",
    )
    cst = fields.Selection(selection=NAT_REC_TABLES, string="CST", required=True)
    ncm_prefix = fields.Char(
        string="Prefixo do NCM",
        help="Só dígitos. Vazio vale para todo NCM do CST; o prefixo mais longo "
        "que casar com o NCM do produto vence.",
    )
    nat_rec = fields.Char(
        string="Natureza da receita",
        size=3,
        required=True,
        help="Código de 3 posições da tabela do CST (4.3.10 a 4.3.16).",
    )
    note = fields.Char(string="Fundamento legal")

    @api.model
    def _find(self, company, cst, ncm_code):
        rules = self.search(
            [("cst", "=", cst), ("company_id", "in", (company.id, False))]
        )
        best = None
        for rule in rules:
            prefix = "".join(ch for ch in (rule.ncm_prefix or "") if ch.isdigit())
            if not (ncm_code or "").startswith(prefix):
                continue
            # prefixo mais longo vence; a regra da empresa vence a geral
            rank = (len(prefix), bool(rule.company_id))
            if best is None or rank > best[0]:
                best = (rank, rule)
        return best[1].nat_rec if best else ""
