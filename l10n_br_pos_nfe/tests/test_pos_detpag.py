# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_br_pos.tests.test_pos_order_invoice import TestPosOrderInvoice


@tagged("post_install", "-at_install")
class TestPosDetPag(TestPosOrderInvoice):
    """O que foi cobrado no balcão precisa chegar ao detPag da nota."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method.fiscal_payment_form = "03"

    def test_payment_becomes_a_detpag(self):
        order = self._sell()
        detpag = order.account_move.fiscal_document_id.nfe40_detPag

        self.assertEqual(len(detpag), 1)
        self.assertEqual(detpag.nfe40_tPag, "03")
        self.assertAlmostEqual(detpag.nfe40_vPag, 100.0, places=2)

    def test_card_is_always_a_vista(self):
        """Cartão parcelado é à vista para o emitente: indPag 0."""
        order = self._sell(pay=False)
        order.add_payment(
            {
                "amount": 100.0,
                "payment_method_id": self.payment_method.id,
                "pos_order_id": order.id,
            }
        )
        order.payment_ids[:1].installments = 6
        order.action_pos_order_paid()
        order.with_context(generate_pdf=False)._generate_pos_order_invoice()
        detpag = order.account_move.fiscal_document_id.nfe40_detPag
        self.assertEqual(detpag.nfe40_indPag, "0")

    def test_card_group_carries_what_was_informed(self):
        order = self._sell(pay=False)
        order.add_payment(
            {
                "amount": 100.0,
                "payment_method_id": self.payment_method.id,
                "pos_order_id": order.id,
            }
        )
        order.payment_ids[:1].write(
            {"card_authorization": "987654", "card_brand": "02"}
        )
        order.action_pos_order_paid()
        order.with_context(generate_pdf=False)._generate_pos_order_invoice()
        card = order.account_move.fiscal_document_id.nfe40_detPag.nfe40_card

        self.assertTrue(card, "O grupo card não foi montado.")
        self.assertEqual(card.nfe40_cAut, "987654")
        self.assertEqual(card.nfe40_tBand, "02")
        self.assertEqual(card.nfe40_tpIntegra, "2")

    def test_each_payment_becomes_its_own_group(self):
        """Cartão + PIX, ou dois cartões: um detPag por pagamento."""
        diario = self.env["account.journal"].create(
            {
                "name": "PIX (teste)",
                "code": "PIXT",
                "type": "bank",
                "company_id": self.company.id,
            }
        )
        pix = self.env["pos.payment.method"].create(
            {
                "name": "PIX (teste)",
                "company_id": self.company.id,
                "fiscal_payment_form": "17",
                "journal_id": diario.id,
            }
        )
        self.config.payment_method_ids = [Command.link(pix.id)]
        order = self._sell(price=100.0, pay=False)
        order.add_payment(
            {
                "amount": 60.0,
                "payment_method_id": self.payment_method.id,
                "pos_order_id": order.id,
            }
        )
        order.add_payment(
            {"amount": 40.0, "payment_method_id": pix.id, "pos_order_id": order.id}
        )
        order.action_pos_order_paid()
        order.with_context(generate_pdf=False)._generate_pos_order_invoice()

        detpag = order.account_move.fiscal_document_id.nfe40_detPag
        self.assertEqual(len(detpag), 2)
        self.assertEqual(sorted(detpag.mapped("nfe40_tPag")), ["03", "17"])
        self.assertAlmostEqual(sum(detpag.mapped("nfe40_vPag")), 100.0, places=2)
