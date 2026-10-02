# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBranchConsolidation(TransactionCase):
    """PIS/COFINS: a matriz apura os lançamentos das filiais escolhidas."""

    def test_period_context_includes_branches(self):
        matriz = self.env["res.company"].create({"name": "Matriz fictícia"})
        filial = self.env["res.company"].create(
            {"name": "Filial fictícia", "parent_id": matriz.id}
        )
        group = self.env["account.tax.group"].create(
            {"name": "PIS fictício", "company_id": matriz.id}
        )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": matriz.id,
                "tax_group_id": group.id,
                "date_from": date(2026, 9, 1),
                "date_to": date(2026, 9, 30),
            }
        )
        self.assertEqual(assessment._get_period_context()["company_ids"], matriz.ids)
        assessment.branch_company_ids = filial
        self.assertEqual(
            sorted(assessment._get_period_context()["company_ids"]),
            sorted((matriz | filial).ids),
        )
