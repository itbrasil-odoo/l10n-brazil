# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _compute_nfe40_detpag(self):
        """O detPag da venda de balcão é o que foi recebido no caixa.

        O ``l10n_br_account_nfe`` monta um único grupo a partir do modo de
        pagamento da fatura e, sem modo de pagamento, declara "sem pagamento"
        (tPag 90). A fatura do PDV não tem modo de pagamento: tem os
        pagamentos do pedido, que o ``l10n_br_pos_nfe`` já levou ao documento,
        um grupo por pagamento. Recalcular aqui apagaria a forma de pagamento
        real da nota.
        """
        from_pos = self.filtered(lambda doc: doc.sudo().move_ids.pos_order_ids)
        return super(FiscalDocument, self - from_pos)._compute_nfe40_detpag()
