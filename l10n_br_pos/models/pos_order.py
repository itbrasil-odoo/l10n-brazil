# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    fiscal_operation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.operation",
        string="Operação Fiscal",
        compute="_compute_fiscal_operation_id",
        store=True,
        readonly=False,
        domain=[
            ("state", "=", "approved"),
            ("fiscal_operation_type", "=", "out"),
        ],
    )

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
