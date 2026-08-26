# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, models

from odoo.addons.l10n_br_pos.constants import FISCAL_PAYMENT_FORM_WITH_CARD


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        detpag = self._prepare_nfe_detpag()
        if detpag:
            vals["nfe40_detPag"] = detpag
        return vals

    def _prepare_nfe_detpag(self):
        """Um grupo detPag por pagamento, na ordem em que foram recebidos.

        O leiaute admite repetir a mesma forma — dois cartões numa venda são
        dois grupos, não um só somado.
        """
        self.ensure_one()
        # Elevado: o grupo card é registro do spec da NF-e, e quem opera o
        # caixa não é gerente de NF-e.
        order = self.sudo()
        commands = []
        for payment in order.payment_ids:
            if not payment.fiscal_payment_form:
                continue
            values = {
                # Cartão parcelado é à vista para o emitente: o parcelamento
                # é entre o cliente e o banco emissor.
                "nfe40_indPag": "0",
                "nfe40_tPag": payment.fiscal_payment_form,
                "nfe40_vPag": payment.amount,
            }
            card = self._prepare_nfe_card(payment)
            if card:
                values["nfe40_card"] = self.env["nfe.40.card"].sudo().create(card).id
            commands.append(Command.create(values))
        return commands

    def _prepare_nfe_card(self, payment):
        if payment.fiscal_payment_form not in FISCAL_PAYMENT_FORM_WITH_CARD:
            return None
        if not (payment.card_authorization or payment.card_brand):
            return None
        return {
            "nfe40_tpIntegra": "2",
            "nfe40_cAut": payment.card_authorization or False,
            "nfe40_tBand": payment.card_brand or False,
        }
