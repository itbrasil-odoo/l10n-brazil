# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _prepare_invoice_vals(self):
        """A fatura já nasce apontando para o pedido.

        O core só grava ``account_move`` no pedido depois de criar a fatura.
        Nesse intervalo o documento fiscal ainda não seria reconhecido como de
        balcão, e o campo calculado do ``l10n_br_account_nfe`` trocaria os
        pagamentos do caixa por um "sem pagamento". Com o vínculo desde a
        criação ele nunca chega a recalcular: nada é apagado para ser refeito
        depois, o que perderia a autorização e a bandeira do cartão.
        """
        vals = super()._prepare_invoice_vals()
        vals["pos_order_ids"] = [Command.link(self.id)]
        return vals
