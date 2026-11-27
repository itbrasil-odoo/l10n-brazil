# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class PartnerSyncTest(TransactionCase):
    """Odoo 20.0 behaviours of res.partner that l10n_br_base refines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"].with_context(tracking_disable=True)
        cls.br = cls.env.ref("base.br")
        cls.cnpj = "93.429.799/0001-17"
        cls.cpf = "705.311.605-05"
        cls.company = cls.Partner.create(
            {"name": "Empresa BR", "vat": cls.cnpj, "country_id": cls.br.id}
        )

    def test_contact_cpf_does_not_replace_company_cnpj(self):
        """A contact with its own CPF never pushes it to its company."""
        contact = self.Partner.create(
            {
                "name": "João",
                "parent_id": self.company.id,
                "vat": self.cpf,
                "country_id": self.br.id,
            }
        )
        self.assertEqual(self.company.cnpj_cpf_stripped, "93429799000117")
        self.assertTrue(self.company.is_company)
        self.assertEqual(contact.cnpj_cpf_stripped, "70531160505")

    def test_foreign_partner_with_cpf_like_vat_is_company(self):
        """The CPF rule for is_company applies to Brazilian partners only."""
        foreign = self.Partner.create(
            {
                "name": "Foreign Co",
                "vat": "70531160505",
                "country_id": self.env.ref("base.us").id,
            }
        )
        self.assertTrue(foreign.is_company)

    def test_disabled_validation_keeps_foreign_vat_check(self):
        """Disabling the Brazilian CPF/CNPJ validation keeps the core check of
        the other countries."""
        self.env["ir.config_parameter"].sudo().set_bool(
            "l10n_br_base.disable_cpf_cnpj_validation", True
        )
        self.Partner.create(
            {"name": "Legacy BR", "vat": "123", "country_id": self.br.id}
        )
        with self.assertRaises(ValidationError):
            self.Partner.create(
                {
                    "name": "Belgian Co",
                    "vat": "BE123",
                    "country_id": self.env.ref("base.be").id,
                }
            )

    def test_copy_several_partners(self):
        """Duplicating several partners at once works and clears the CNPJ."""
        other = self.Partner.create(
            {"name": "Other", "vat": "06.990.590/0001-23", "country_id": self.br.id}
        )
        copies = (self.company | other).copy()
        self.assertEqual(len(copies), 2)
        self.assertFalse(any(copies.mapped("vat")))

    def test_multi_ie_checks_every_partner_with_the_cnpj(self):
        """With allow_cnpj_multi_ie, a duplicated IE is refused whatever the
        partner the search finds first."""
        self.env["ir.config_parameter"].sudo().set_bool(
            "l10n_br_base.allow_cnpj_multi_ie", True
        )
        vals = {
            "vat": "06.990.590/0001-23",
            "country_id": self.br.id,
            "state_id": self.env.ref("base.state_br_sp").id,
        }
        self.Partner.create(dict(vals, name="A", l10n_br_ie_code="932.446.119.086"))
        self.Partner.create(dict(vals, name="B", l10n_br_ie_code="041.092.540.590"))
        with self.assertRaises(ValidationError):
            self.Partner.create(dict(vals, name="C", l10n_br_ie_code="041.092.540.590"))
