# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from ..constants import FISCAL_PAYMENT_FORM


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    fiscal_payment_form = fields.Selection(
        selection=FISCAL_PAYMENT_FORM,
        string="Forma de Pagamento (SEFAZ)",
        help="Forma que a nota informa para os pagamentos feitos por este meio.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        # A lista do core é real (não vazia), então acrescentar preserva o resto.
        return super()._load_pos_data_fields(config_id) + ["fiscal_payment_form"]
