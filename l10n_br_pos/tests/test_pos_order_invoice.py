# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosOrderInvoice(TransactionCase):
    """A venda de balcão precisa virar documento fiscal.

    Sem a ponte deste módulo a fatura é lançada sem operação fiscal e sem tipo
    de documento — e, o que torna a falha perigosa, **sem erro nenhum**. Estes
    testes afirmam que o documento fiscal existe, e não apenas que o
    faturamento não estourou.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.fiscal_operation = cls.env.ref("l10n_br_fiscal.fo_venda")
        cls.env.user.company_ids = [Command.link(cls.company.id)]
        cls.env.user.company_id = cls.company

        # As empresas de demonstração brasileiras não trazem armazém, e o PDV
        # exige um para resolver o tipo de operação de estoque.
        if not cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ):
            cls.env["stock.warehouse"].create(
                {
                    "name": "Balcão",
                    "code": "BLC",
                    "company_id": cls.company.id,
                }
            )

        cls.partner = cls.env["res.partner"].create({"name": "Cliente de Balcão"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Produto de Balcão",
                "type": "consu",
                "available_in_pos": True,
                "list_price": 100.0,
                "taxes_id": [Command.clear()],
            }
        )
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Dinheiro (teste)",
                "company_id": cls.company.id,
                "journal_id": cls.env["account.journal"]
                .search(
                    [("type", "=", "cash"), ("company_id", "=", cls.company.id)],
                    limit=1,
                )
                .id,
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Balcão (teste)",
                "company_id": cls.company.id,
                "payment_method_ids": [Command.set(cls.payment_method.ids)],
                "out_pos_fiscal_operation_id": cls.fiscal_operation.id,
            }
        )

    def _sell(self, price=100.0):
        """Uma venda de balcão paga e faturada, como o PDV a produz."""
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.uid}
        )
        session.action_pos_session_open()
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "to_invoice": True,
                "amount_tax": 0.0,
                "amount_total": price,
                "amount_paid": price,
                "amount_return": 0.0,
                "lines": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "qty": 1,
                            "price_unit": price,
                            "price_subtotal": price,
                            "price_subtotal_incl": price,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        order.add_payment(
            {
                "amount": price,
                "payment_method_id": self.payment_method.id,
                "pos_order_id": order.id,
            }
        )
        order.action_pos_order_paid()
        order.with_context(generate_pdf=False)._generate_pos_order_invoice()
        return order

    def test_invoice_from_pos_sale_is_a_fiscal_document(self):
        """A fatura gerada por uma venda de balcão carrega o documento fiscal."""
        move = self._sell().account_move

        self.assertTrue(
            move.fiscal_operation_id,
            "A fatura saiu sem operação fiscal: sem ela o l10n_br_fiscal não "
            "determina CFOP nem imposto, e a nota não é emissível.",
        )
        self.assertTrue(
            move.document_type_id,
            "A fatura saiu sem tipo de documento: é um lançamento contábil "
            "comum, não um documento fiscal.",
        )
        self.assertTrue(
            move.fiscal_document_id,
            "A fatura saiu sem documento fiscal associado — não há o que emitir.",
        )
