# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def write(self, vals):
        result = super().write(vals)
        if "state_edoc" in vals:
            self._notify_pos_sessions()
        return result

    def _notify_pos_sessions(self):
        """Empurra a nova situação para os pontos de venda abertos.

        A autorização chega depois da venda, de forma assíncrona. Sem o
        empurrão o operador só descobre o resultado ao reabrir o balcão.
        """
        orders = self.env["pos.order"].search(
            [("account_move.fiscal_document_id", "in", self.ids)]
        )
        for config in orders.config_id:
            session = config.current_session_id
            if not session:
                continue
            config.notify_synchronisation(
                session.id,
                0,
                {
                    "pos.order": orders.filtered(
                        lambda o, c=config: o.config_id == c
                    ).ids
                },
            )
