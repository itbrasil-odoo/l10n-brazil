# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..constants import (
    FISCAL_CARD_BRAND,
    FISCAL_PAYMENT_FORM,
    FISCAL_PAYMENT_FORM_WITH_CARD,
)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    fiscal_payment_form = fields.Selection(
        selection=FISCAL_PAYMENT_FORM,
        string="Forma de Pagamento (SEFAZ)",
        compute="_compute_fiscal_payment_form",
        store=True,
        readonly=False,
    )
    card_authorization = fields.Char(
        string="Código de Autorização",
        size=20,
        help="Código devolvido pela credenciadora na captura (NSU). "
        "Não é único e pode repetir, então não serve sozinho como chave de "
        "conciliação.",
    )
    card_brand = fields.Selection(
        selection=FISCAL_CARD_BRAND,
        string="Bandeira",
    )
    installments = fields.Integer(
        string="Parcelas",
        help="Controle interno. A NF-e não carrega o parcelamento do cartão: "
        "para o emitente a venda é à vista, e o parcelamento é entre o cliente "
        "e o banco emissor.",
    )

    @api.depends("payment_method_id")
    def _compute_fiscal_payment_form(self):
        for payment in self:
            payment.fiscal_payment_form = payment.payment_method_id.fiscal_payment_form

    @api.constrains("fiscal_payment_form", "card_authorization", "card_brand")
    def _check_card_data_is_allowed(self):
        for payment in self:
            if not (payment.card_authorization or payment.card_brand):
                continue
            if payment.fiscal_payment_form in FISCAL_PAYMENT_FORM_WITH_CARD:
                continue
            raise ValidationError(
                _(
                    "Dados de cartão informados numa forma de pagamento que não "
                    "admite o grupo: %(forma)s. A SEFAZ recusa a nota "
                    "(rejeição 963).",
                    forma=dict(FISCAL_PAYMENT_FORM).get(
                        payment.fiscal_payment_form, _("não informada")
                    ),
                )
            )
