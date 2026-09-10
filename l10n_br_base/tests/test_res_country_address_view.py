# Copyright (C) 2026 - TODAY  IT Brasil
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests.common import TransactionCase


class TestResCountryAddressView(TransactionCase):
    def test_brazil_points_at_the_brazilian_address_view(self):
        self.assertEqual(
            self.env.ref("base.br").address_view_id,
            self.env.ref("l10n_br_base.l10n_br_base_res_partner_address"),
        )

    def test_partner_form_carries_the_brazilian_address_fields(self):
        self.env.company.country_id = self.env.ref("base.br")
        # get_view's cache key holds the company, not its country.
        self.env.registry.clear_cache()
        self.addCleanup(self.env.registry.clear_cache)
        arch = self.env["res.partner"].get_view(
            self.env.ref("base.view_partner_form").id, "form"
        )["arch"]
        for field in ("street_name", "street_number", "district", "city_id"):
            self.assertIn('name="%s"' % field, arch)
