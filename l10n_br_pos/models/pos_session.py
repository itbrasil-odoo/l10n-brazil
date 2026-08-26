# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class PosSession(models.Model):
    _inherit = "pos.session"

    def _get_receivable_account(self, payment_method):
        """Explica a configuração que falta em vez de estourar no banco.

        O plano de contas brasileiro base (``br_oca``) não traz conta a receber
        nenhuma — diferente de ``br_oca_generic`` e ``br_oca_simple``, que a
        definem. A empresa fica então sem
        ``account_default_pos_receivable_account_id`` e, se o meio de pagamento
        também não tiver conta, a linha de recebível nasce sem conta.

        O fechamento da sessão morre numa violação de constraint do Postgres,
        que chega ao operador do caixa como "Conta necessária ausente na linha
        contábil" — sem dizer onde mexer, e no pior momento possível, com o
        caixa cheio e a sessão travada.
        """
        account = super()._get_receivable_account(payment_method)
        if not account:
            raise UserError(
                _(
                    "O meio de pagamento “%(method)s” não tem Conta a Receber, e "
                    "a empresa “%(company)s” também não define uma.\n\n"
                    "Configure a Conta a Receber do ponto de venda na empresa "
                    "(Contabilidade → Configurações), ou uma conta no próprio "
                    "meio de pagamento.\n\n"
                    "O plano de contas brasileiro básico não cria essa conta, "
                    "então ela precisa ser escolhida à mão.",
                    method=payment_method.display_name,
                    company=self.company_id.display_name,
                )
            )
        return account
