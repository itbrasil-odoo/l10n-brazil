# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    # O mixin fiscal traz o que a linha precisa para se determinar — a começar
    # por ``ind_final``, que a linha lê do documento a que pertence.
    _name = "pos.order"
    _inherit = [_name, "l10n_br_fiscal.document.mixin"]

    @api.model
    def _fiscal_operation_domain(self):
        return [
            ("fiscal_operation_type", "=", "out"),
            ("state", "=", "approved"),
            ("fiscal_type", "not ilike", "%refund%"),
        ]

    fiscal_operation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.operation",
        compute="_compute_fiscal_operation_id",
        store=True,
        readonly=False,
        # Sem precompute, todo campo precompute=True do mixin fiscal que depende
        # da operação cai em cascata para computo pós-insert.
        precompute=True,
        domain=lambda self: self._fiscal_operation_domain(),
    )

    l10n_br_emit_document = fields.Boolean(
        string="Emitir documento fiscal",
        copy=False,
        help="Transmite o documento fiscal assim que a venda gera a fatura. "
        "Sem isto o documento é montado e fica pendente de envio.",
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        return super()._load_pos_data_fields(config_id) + ["l10n_br_emit_document"]

    @api.model
    def _get_fiscal_lines_field_name(self):
        """O ponto de venda chama de ``lines`` o que o mixin espera em
        ``fiscal_line_ids``."""
        return "lines"

    @api.depends("session_id", "fiscal_operation_id")
    def _compute_document_type_id(self):
        """Documento escolhido no ponto de venda, com o padrão da empresa atrás.

        O mixin resolve só pela empresa, o que faz toda venda sair no mesmo
        documento. Um balcão que vende serviço precisa de NFS-e sem que a
        empresa inteira mude de padrão.
        """
        result = super()._compute_document_type_id()
        for order in self:
            document_type = order.session_id.config_id.out_pos_document_type_id
            if document_type:
                order.document_type_id = document_type
        return result

    @api.depends("session_id")
    def _compute_fiscal_operation_id(self):
        for order in self:
            order.fiscal_operation_id = (
                order.session_id.config_id.out_pos_fiscal_operation_id
            )

    def _prepare_invoice_vals(self):
        """Leva a operação fiscal da venda para a fatura.

        Sem isto o ``account.move`` gerado pelo ponto de venda nasce sem
        documento fiscal — e é lançado sem erro, o que faz a venda desaparecer
        da apuração sem que ninguém seja avisado.
        """
        vals = super()._prepare_invoice_vals()
        operation = self.fiscal_operation_id
        if not operation:
            return vals

        vals["fiscal_operation_id"] = operation.id
        document_type = self.document_type_id or self.company_id.document_type_id
        if document_type:
            vals["document_type_id"] = document_type.id
            document_serie = document_type.get_document_serie(
                self.company_id, operation
            )
            if document_serie:
                vals["document_serie_id"] = document_serie.id
        if operation.journal_id:
            vals["journal_id"] = operation.journal_id.id
        return vals

    def _get_invoice_lines_values(self, line_values, pos_order_line):
        """Leva os campos fiscais da linha de venda para a linha da fatura.

        A operação no cabeçalho não basta: é a linha que resolve CFOP, CST e
        imposto por produto. Os valores do ponto de venda prevalecem sobre os
        do dicionário fiscal — quantidade e preço são o que foi efetivamente
        cobrado no balcão.
        """
        vals = super()._get_invoice_lines_values(line_values, pos_order_line)
        if not pos_order_line.fiscal_operation_id:
            return vals
        fiscal_vals = pos_order_line._prepare_br_fiscal_dict()
        fiscal_vals.update(vals)
        return fiscal_vals

    def _generate_pos_order_invoice(self):
        result = super()._generate_pos_order_invoice()
        to_emit = self.filtered("l10n_br_emit_document")
        if to_emit:
            to_emit._l10n_br_send_fiscal_documents()
        return result

    def _l10n_br_send_fiscal_documents(self):
        """Transmite o documento fiscal das vendas marcadas para emitir.

        Falha de transmissão não derruba a venda. A SEFAZ cai, rejeita e fica
        lenta; o balcão não pode parar junto. O documento permanece pendente,
        para ser retransmitido depois, e o motivo fica registrado na fatura —
        que é onde quem for retransmitir vai procurar.

        Cada envio roda no seu próprio savepoint: sem isso, uma exceção depois
        de escritas parciais envenena a transação e leva embora a fatura que
        acabou de ser criada.
        """
        if not self.env.user.has_group("l10n_br_pos.group_pos_emit_document"):
            raise AccessError(
                _(
                    "Você não tem permissão para emitir documento fiscal pelo "
                    "ponto de venda. A venda pode ser faturada normalmente: o "
                    "documento fica pendente para quem tiver a permissão "
                    "transmitir."
                )
            )
        for order in self:
            move = order.account_move
            if not move or not move.fiscal_document_id:
                continue
            try:
                with self.env.cr.savepoint():
                    move.action_document_send()
            except Exception as error:  # noqa: BLE001 - ver docstring
                _logger.warning(
                    "PDV %s: falha ao transmitir o documento fiscal da fatura "
                    "%s, que fica pendente de envio: %s",
                    order.name,
                    move.name,
                    error,
                )
                move.message_post(
                    body=_(
                        "Falha ao transmitir o documento fiscal pelo ponto de "
                        "venda. O documento continua pendente de envio.\n\n%s"
                    )
                    % error
                )
