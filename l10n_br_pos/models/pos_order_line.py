# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class PosOrderLine(models.Model):
    _name = "pos.order.line"
    _inherit = [_name, "l10n_br_fiscal.document.line.mixin"]

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

    # O mixin resolve a operação de linha a partir do parceiro, e a venda de
    # balcão guarda o parceiro no pedido, não na linha.
    partner_id = fields.Many2one(
        related="order_id.partner_id",
        depends=["order_id.partner_id"],
    )

    # Adapta os campos do mixin aos nomes que o ponto de venda já usa.
    quantity = fields.Float(
        string="Product Uom Quantity",
        related="qty",
        depends=["qty"],
    )

    uom_id = fields.Many2one(
        related="product_uom_id",
        depends=["product_uom_id"],
    )

    # Tabelas de relação explícitas: sem elas dois m2m para o mesmo comodel
    # colidem na geração automática do nome.
    fiscal_tax_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.tax",
        relation="pos_order_line_fiscal_tax_rel",
        column1="pos_order_line_id",
        column2="fiscal_tax_id",
        string="Fiscal Taxes",
    )

    comment_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.comment",
        relation="pos_order_line_fiscal_comment_rel",
        column1="pos_order_line_id",
        column2="comment_id",
        string="Comments",
    )

    # O mixin lê ``ind_final`` do documento a que a linha pertence; na venda de
    # balcão esse documento é o próprio pedido do ponto de venda.
    def _get_document(self):
        self.ensure_one()
        return self.order_id

    def _get_total_for_tax_totals(self):
        """O total do documento a que esta linha pertence.

        ``l10n_br_account._get_tax_totals_summary`` decide se a linha é fiscal
        olhando ``fiscal_operation_line_id`` e, quando é, chama este método —
        dois atributos diferentes, e o contrato entre eles nunca foi escrito.
        Até este módulo existir ele se sustentava por coincidência: todo modelo
        que ganhava o mixin de linha fiscal (``account.move.line``,
        ``sale.order.line``, ``purchase.order.line``) também implementava o
        método.

        ``pos.order.line`` foi o primeiro a ter um sem o outro, e o resultado
        era a tela de pagamento do balcão morrer com ``'pos.order.line' object
        has no attribute '_get_total_for_tax_totals'`` — no meio da venda, com
        o troco já na tela.

        Sem ``@api.model``, ao contrário das três implementações irmãs: o método
        lê ``self.order_id``, então opera sobre registros, e o decorador ali é
        engano herdado por cópia.
        """
        self.ensure_one()
        return self.order_id.amount_total

    @api.depends("order_id.fiscal_operation_id")
    def _compute_fiscal_operation_id(self):
        for line in self:
            line.fiscal_operation_id = line.order_id.fiscal_operation_id
