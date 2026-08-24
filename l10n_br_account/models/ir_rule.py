# Copyright (C) 2026 - TODAY Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, tools
from odoo.tools import config


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    @tools.conditional(
        "xml" not in config["dev_mode"],
        tools.ormcache(
            "self.env.uid",
            "self.env.su",
            "model_name",
            "mode",
            # allow_fiscal_access MUDA o resultado para os modelos fiscais, entao
            # PRECISA entrar na chave. Sem ele as duas situacoes compartilhavam a
            # mesma entrada e quem computasse primeiro definia o resultado da outra:
            #
            #   fiscal primeiro -> a entrada guarda o dominio real, e o
            #     _compute_domain de account.move(.line) recebe esse dominio na
            #     recursao do _inherits, virando
            #     ('fiscal_document_line_id', 'any', [...]). Como as linhas sem
            #     documento fiscal (prazo, imposto, secao) tem o campo NULL, o
            #     'any' da falso e QUALQUER write nelas e negado -> AccessError ao
            #     confirmar fatura ("registros ultrassecretos").
            #
            #   contabil primeiro -> a entrada guarda [], e uma consulta DIRETA a
            #     l10n_br_fiscal.document(.line) passa a rodar sem regra: o
            #     isolamento multiempresa fica desligado ate o cache ser limpo.
            #
            # Como o cache e por processo, o comportamento variava de worker para
            # worker e parecia intermitente.
            "self._context.get('allow_fiscal_access')",
            "tuple(self._compute_domain_context_values())",
        ),
    )
    def _compute_domain(self, model_name, mode="read"):
        if model_name in ("account.move", "account.move.line"):
            return super(
                IrRule, self.with_context(allow_fiscal_access=True)
            )._compute_domain(model_name, mode)
        if model_name in (
            "l10n_br_fiscal.document",
            "l10n_br_fiscal.document.line",
        ) and self._context.get("allow_fiscal_access"):
            return []
        return super()._compute_domain(model_name, mode)
