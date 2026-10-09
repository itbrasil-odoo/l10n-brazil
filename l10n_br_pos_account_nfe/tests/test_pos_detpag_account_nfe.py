# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.l10n_br_pos.tests.test_pos_order_invoice import TestPosOrderInvoice


@tagged("post_install", "-at_install")
class TestPosDetPagAccountNfe(TestPosOrderInvoice):
    """Os pagamentos do balcão sobrevivem ao detPag do financeiro."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method.fiscal_payment_form = "03"

    def test_counter_payment_is_not_replaced_by_no_payment(self):
        """Era o defeito: a nota do balcão saía com tPag 90, sem pagamento."""
        order = self._sell()
        detpag = order.account_move.fiscal_document_id.nfe40_detPag

        self.assertEqual(detpag.mapped("nfe40_tPag"), ["03"])
        self.assertAlmostEqual(detpag.nfe40_vPag, 100.0, places=2)

    def test_recompute_keeps_the_counter_payment(self):
        """Depois de faturada, um recálculo não pode voltar ao "sem pagamento"."""
        order = self._sell()
        document = order.account_move.fiscal_document_id

        document._compute_nfe40_detpag()

        self.assertEqual(document.nfe40_detPag.mapped("nfe40_tPag"), ["03"])

    def test_invoice_outside_the_counter_is_untouched(self):
        """Fatura que não vem do PDV segue a regra do financeiro."""
        order = self._sell()
        document = order.account_move.fiscal_document_id
        outros = self.env["l10n_br_fiscal.document"].search(
            [("id", "!=", document.id), ("move_ids", "!=", False)], limit=1
        )
        if not outros:
            self.skipTest("database without another invoiced fiscal document")
        self.assertFalse(outros.sudo().move_ids.pos_order_ids)
        antes = outros.nfe40_detPag.mapped("nfe40_tPag")

        outros._compute_nfe40_detpag()

        self.assertEqual(outros.nfe40_detPag.mapped("nfe40_tPag"), antes)
