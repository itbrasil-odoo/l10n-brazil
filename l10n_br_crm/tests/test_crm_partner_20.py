# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class CrmLeadPartner20Test(TransactionCase):
    """Odoo 20.0 Lead/partner flows refined by l10n_br_crm."""

    def test_foreign_lead_creates_its_company(self):
        """A Lead without CNPJ keeps the core flow: the company is created
        from the Lead company name."""
        lead = self.env["crm.lead"].create(
            {
                "name": "Foreign Lead",
                "contact_name": "John",
                "partner_name": "Acme Inc",
                "country_id": self.env.ref("base.us").id,
            }
        )
        contact = lead._create_customer()
        self.assertEqual(contact.name, "John")
        self.assertEqual(contact.parent_id.name, "Acme Inc")

    def test_customer_without_parent_keeps_lead_data(self):
        """Picking a customer that is not a company and has no parent keeps
        the company name and website typed on the Lead."""
        lead = self.env["crm.lead"].create(
            {
                "name": "Lead",
                "partner_name": "Acme",
                "website": "http://acme.example.com",
            }
        )
        person = self.env["res.partner"].create({"name": "Maria"})
        self.assertFalse(person.is_company)
        lead.partner_id = person
        lead._onchange_partner_id()
        self.assertEqual(lead.partner_name, "Acme")
        self.assertEqual(lead.website, "http://acme.example.com")
