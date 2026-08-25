# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    out_pos_fiscal_operation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.operation",
        string="Operação Fiscal de Venda",
        domain=[
            ("state", "=", "approved"),
            ("fiscal_operation_type", "=", "out"),
        ],
        help="Operação fiscal aplicada às vendas deste ponto de venda. É ela "
        "que leva CFOP, CST e impostos à nota gerada a partir da venda; sem "
        "operação a fatura é lançada como documento não fiscal.",
    )
