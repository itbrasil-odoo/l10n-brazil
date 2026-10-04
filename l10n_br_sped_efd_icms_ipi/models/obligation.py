# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Guia Prático 3.2.4: E116 (ICMS próprio), E250 (ICMS-ST) e E316 (DIFAL e
# FCP) levam a data de vencimento e o "código de receita referente à
# obrigação, próprio da unidade da federação". Os dois dependem da UF e do
# regime do contribuinte, então são configuração da empresa, não regra do
# módulo: aqui ficam uma vez, em vez de digitados a cada declaração.
OBLIGATION_KINDS = [
    ("icms", "ICMS próprio (E116)"),
    ("st", "ICMS-ST (E250)"),
    ("difal", "DIFAL (E316, obrigação 000)"),
    ("fcp", "FCP (E316, obrigação 006)"),
]


class EfdIcmsIpiObligation(models.Model):
    _name = "l10n_br_sped_efd_icms_ipi.obligation"
    _description = "EFD ICMS/IPI: código de receita e vencimento por obrigação"
    _order = "company_id, kind, state_id"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    kind = fields.Selection(OBLIGATION_KINDS, string="Obrigação", required=True)
    state_id = fields.Many2one(
        "res.country.state",
        string="UF",
        domain="[('country_id.code', '=', 'BR')]",
        help="UF da tabela de códigos de receita: a da empresa para ICMS "
        "próprio e ST; a de destino para DIFAL e FCP. Vazio vale para "
        "qualquer UF sem regra própria.",
    )
    cod_receita = fields.Char(
        string="Código de receita",
        required=True,
        help="Da tabela de códigos de receita da UF publicada no SPED (em MG, "
        "tabela 17254; ex.: 1206 ICMS comércio, 2204 ICMS-ST comércio). "
        "Confirme com o contador.",
    )
    due_day = fields.Integer(string="Dia do vencimento", required=True)
    due_months = fields.Integer(
        string="Meses após o período",
        default=1,
        required=True,
        help="1 = no mês seguinte ao período apurado.",
    )
    active = fields.Boolean(default=True)

    @api.constrains("due_day", "due_months")
    def _check_due(self):
        for rule in self:
            if not 1 <= rule.due_day <= 31 or rule.due_months < 0:
                raise ValidationError(
                    self.env._("Dia de vencimento entre 1 e 31 e meses não negativos.")
                )

    def due_date(self, period_end):
        """Vencimento da obrigação do período que termina em `period_end`."""
        self.ensure_one()
        month = period_end + relativedelta(months=self.due_months)
        last = calendar.monthrange(month.year, month.month)[1]
        return date(month.year, month.month, min(self.due_day, last))

    @api.model
    def find(self, company, kind, uf_code=None):
        """A regra da UF, ou a sem UF; vazio se não houver."""
        rules = self.search([("company_id", "=", company.id), ("kind", "=", kind)])
        exact = rules.filtered(lambda rule: rule.state_id.code == uf_code)
        return (exact or rules.filtered(lambda rule: not rule.state_id))[:1]
