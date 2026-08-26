# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo import Command, _
from odoo.exceptions import AccessError, UserError
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
        # Estes testes medem a ponte entre a venda de balcão e a fatura, não a
        # integração EDI. Com o processador "oca", postar a fatura confirma o
        # documento e dispara o serializador da NF-e
        # (_exec_before_SITUACAO_EDOC_A_ENVIAR → l10n_br_nfe._document_export),
        # que quebra porque a operação de demonstração não define ICMS — falha
        # de configuração fiscal do demo, não da ponte. "Sem Integração" tira o
        # EDI do caminho; a transmissão é coberta à parte, com mock.
        cls.company.processador_edoc = "nenhum"
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
        # Sem tipo fiscal nenhuma linha da operação casa e a determinação
        # devolve vazio — que é o que estes testes precisam distinguir de uma
        # ponte quebrada.
        #
        # Mercadoria para revenda, que é o que um balcão vende.
        cls.product = cls.env["product.product"].create(
            {
                "name": "Produto de Balcão",
                "type": "consu",
                "available_in_pos": True,
                "list_price": 100.0,
                "taxes_id": [Command.clear()],
                "fiscal_type": "00",
                "ncm_id": cls.env.ref("l10n_br_fiscal.ncm_22011000").id,
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

    def _sell(self, price=100.0, to_invoice=True, emit=False):
        """Uma venda de balcão paga, faturada ou não, como o PDV a produz."""
        session = self.env["pos.session"].create(
            {"config_id": self.config.id, "user_id": self.env.uid}
        )
        session.action_pos_session_open()
        order = self.env["pos.order"].create(
            {
                "session_id": session.id,
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "to_invoice": to_invoice,
                "l10n_br_emit_document": emit,
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
        if to_invoice:
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

    def test_invoice_line_from_pos_sale_carries_cfop(self):
        """A linha da fatura carrega operação de linha e CFOP.

        A operação no cabeçalho não basta: é a linha que determina CFOP, CST e
        imposto por produto. Sem ela a nota tem operação mas não tem o que
        declarar.
        """
        move = self._sell().account_move
        line = move.invoice_line_ids.filtered(
            lambda aml: aml.product_id == self.product
        )
        self.assertTrue(line, "A fatura saiu sem a linha do produto vendido.")

        self.assertTrue(
            line.fiscal_operation_line_id,
            "A linha da fatura saiu sem operação fiscal de linha: é ela que "
            "resolve CFOP e CST para este produto.",
        )
        self.assertTrue(
            line.cfop_id,
            "A linha da fatura saiu sem CFOP — a nota não tem o que declarar.",
        )

    def test_invoice_takes_document_type_chosen_on_the_pos(self):
        """O documento da fatura é o escolhido no PDV, não o padrão da empresa.

        Um balcão que vende serviço precisa emitir NFS-e mesmo quando o padrão
        da empresa é NF-e — e o contrário, num balcão de peças. Sem isso a
        escolha do documento não existe: toda venda sai no padrão da empresa.
        """
        nfe = self.env.ref("l10n_br_fiscal.document_55")
        nfse = self.env.ref("l10n_br_fiscal.document_SE")
        self.company.document_type_id = nfe
        self.config.out_pos_document_type_id = nfse

        move = self._sell().account_move
        move.invalidate_recordset()

        self.assertEqual(
            move.document_type_id,
            nfse,
            "A fatura saiu no documento padrão da empresa, ignorando o "
            "escolhido no ponto de venda.",
        )

    def test_missing_pos_receivable_account_says_what_to_configure(self):
        """Sem conta a receber do PDV, o erro precisa dizer o que configurar.

        O plano de contas brasileiro base (``br_oca``) não traz conta a receber
        nenhuma, então a empresa fica sem
        ``account_default_pos_receivable_account_id``. O ponto de venda monta a
        linha de recebível sem conta e o fechamento da sessão morre com uma
        violação de not-null no banco — que chega ao operador do caixa como
        "Conta necessária ausente na linha contábil", sem dizer onde mexer.
        """
        self.company.account_default_pos_receivable_account_id = False
        self.payment_method.receivable_account_id = False
        order = self._sell(to_invoice=False)

        with self.assertRaises(UserError) as caught:
            order.session_id.action_pos_session_close()

        message = str(caught.exception)
        self.assertIn(
            "Conta a Receber",
            message,
            f"O erro não diz qual configuração está faltando: {message}",
        )
        self.assertIn(
            self.payment_method.name,
            message,
            f"O erro não diz qual meio de pagamento disparou: {message}",
        )


@tagged("post_install", "-at_install")
class TestPosOrderEmit(TestPosOrderInvoice):
    """Transmitir a NF-e a partir do balcão.

    A venda de balcão monta o documento fiscal e o deixa em ``a_enviar``. Quem
    opera o caixa precisa poder transmitir na hora, quando o cliente pede a
    nota — mas transmitir é ato fiscal, então depende de permissão.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.emit_group = cls.env.ref("l10n_br_pos.group_pos_emit_document")

    def test_flagged_sale_transmits_the_fiscal_document(self):
        """Marcada para emitir, a venda transmite o documento."""
        self.env.user.groups_id = [Command.link(self.emit_group.id)]
        sent = []
        with patch.object(
            type(self.env["account.move"]),
            "action_document_send",
            lambda records: sent.append(records),
        ):
            order = self._sell(emit=True)

        self.assertTrue(sent, "A venda foi marcada para emitir e nada foi transmitido.")
        self.assertIn(order.account_move, sent[0])

    def test_sale_survives_a_failed_transmission(self):
        """SEFAZ fora não pode derrubar a venda: o documento fica pendente."""
        self.env.user.groups_id = [Command.link(self.emit_group.id)]

        def explode(records):
            raise UserError(_("SEFAZ indisponível"))

        with patch.object(
            type(self.env["account.move"]), "action_document_send", explode
        ):
            order = self._sell(emit=True)

        self.assertTrue(
            order.account_move.exists(),
            "A falha na transmissão derrubou a venda inteira — o caixa fica "
            "travado por indisponibilidade da SEFAZ.",
        )
        self.assertTrue(
            order.account_move.fiscal_document_id,
            "A venda perdeu o documento fiscal ao falhar a transmissão.",
        )

    def test_emitting_without_permission_is_refused(self):
        """Sem o grupo, a venda não transmite — e diz por quê."""
        self.env.user.groups_id = [Command.unlink(self.emit_group.id)]
        with self.assertRaises(AccessError):
            self._sell(emit=True)

    def test_operator_without_invoicing_rights_can_transmit(self):
        """O caixa transmite sem ter direito de escrita na fatura.

        Quem opera o balcão não tem (nem deve ter) permissão de faturamento, e
        transmitir escreve em account.move. O core do ponto de venda já cria e
        posta a fatura com sudo(); a transmissão precisa do mesmo tratamento,
        senão a venda termina com "Você não tem permissão para modificar
        registros de Lançamento de diário".

        O sudo executa o que o grupo já autorizou — não substitui a
        autorização, que continua sendo verificada antes.

        Rodar como usuário restrito é o ponto do teste: o TransactionCase é
        superusuário por padrão e passaria sem provar nada.
        """
        operador = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Operadora de Caixa",
                    "login": "caixa_teste",
                    "company_id": self.company.id,
                    "company_ids": [Command.set([self.company.id])],
                    "groups_id": [
                        Command.set(
                            [
                                self.env.ref("base.group_user").id,
                                self.env.ref("point_of_sale.group_pos_user").id,
                                self.emit_group.id,
                            ]
                        )
                    ],
                }
            )
        )
        self.assertFalse(
            operador.has_group("account.group_account_invoice"),
            "O teste perde o sentido se a operadora puder faturar.",
        )

        # A venda é faturada sem emitir: a transmissão é disparada logo abaixo,
        # já como a operadora, que é o que este teste mede.
        order = self._sell(emit=False)

        elevado = []
        with patch.object(
            type(self.env["account.move"]),
            "action_document_send",
            lambda records: elevado.append(records.env.su),
        ):
            order.with_user(operador)._l10n_br_send_fiscal_documents()

        self.assertTrue(elevado, "A transmissão não chegou a ser chamada.")
        self.assertTrue(
            elevado[0],
            "A transmissão rodou com os direitos da operadora, que não pode "
            "escrever em account.move — a venda terminaria em erro de "
            "permissão no lançamento de diário.",
        )
