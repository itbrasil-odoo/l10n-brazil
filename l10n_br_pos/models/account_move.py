# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_br_installments = fields.Integer(
        string="Parcelas",
        compute="_compute_l10n_br_installments",
        store=True,
        help="Parcelamento informado no ponto de venda. Não vai à NF-e.",
    )

    @api.depends("pos_order_ids.payment_ids.installments")
    def _compute_l10n_br_installments(self):
        for move in self:
            parcelas = move.pos_order_ids.payment_ids.mapped("installments")
            move.l10n_br_installments = max(parcelas or [0])
