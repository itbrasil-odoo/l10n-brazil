# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


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
        domain=lambda self: self._fiscal_operation_domain(),
    )

    @api.model
    def _get_fiscal_lines_field_name(self):
        """O ponto de venda chama de ``lines`` o que o mixin espera em
        ``fiscal_line_ids``."""
        return "lines"

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
        document_type = self.company_id.document_type_id
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
