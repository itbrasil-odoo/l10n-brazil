# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_pos_order_invoice import TestPosOrderInvoice


@tagged("post_install", "-at_install")
class TestPosPaymentFiscal(TestPosOrderInvoice):
    """Forma de pagamento SEFAZ e dados de cartão na venda de balcão."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method.fiscal_payment_form = "03"  # cartão de crédito

    def test_payment_takes_the_form_from_its_method(self):
        order = self._sell()
        self.assertEqual(order.payment_ids[:1].fiscal_payment_form, "03")

    def test_card_data_is_optional(self):
        """Cada cliente tem política própria: exigir NSU travaria o caixa."""
        order = self._sell()
        payment = order.payment_ids[:1]
        self.assertFalse(payment.card_authorization)
        self.assertFalse(payment.card_brand)

    def test_card_data_is_kept_when_informed(self):
        order = self._sell()
        payment = order.payment_ids[:1]
        payment.write(
            {"card_authorization": "123456", "card_brand": "02", "installments": 3}
        )
        self.assertEqual(payment.card_authorization, "123456")
        self.assertEqual(payment.card_brand, "02")

    def test_card_data_is_refused_on_a_form_without_card(self):
        """Informar cartão em pagamento que não admite o grupo derruba a nota."""
        self.payment_method.fiscal_payment_form = "01"  # dinheiro
        order = self._sell()
        with self.assertRaises(ValidationError):
            order.payment_ids[:1].write({"card_authorization": "123456"})

    def test_installments_reach_the_invoice(self):
        order = self._sell()
        order.payment_ids[:1].write({"installments": 6})
        order.account_move.invalidate_recordset()
        self.assertEqual(
            order.account_move.l10n_br_installments,
            6,
            "As parcelas não chegaram à fatura.",
        )
