# Copyright 2026 - Renan Teixeira
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDocumentUser(TransactionCase):
    """l10n_br_account turns l10n_br_fiscal.document.user_id into a related of
    proxy_user_id, fed from account.move.invoice_user_id. The salesperson must
    reach the fiscal document however the invoice got one, otherwise templates
    reading ``doc.user_id`` render an empty recordset into the NF-e.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env["res.partner"].create({"name": "Comment fixture partner"})
        cls.salesperson = cls.env["res.users"].create(
            {
                "name": "Fixture Salesperson",
                "login": "fixture.salesperson",
                "groups_id": [(6, 0, cls.env.ref("base.group_user").ids)],
            }
        )
        cls.move_vals = {
            "move_type": "out_invoice",
            "partner_id": cls.partner.id,
            "fiscal_operation_id": cls.env.ref("l10n_br_fiscal.fo_venda").id,
            "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
        }

    def test_user_id_from_invoice_user_id_default(self):
        """The default of invoice_user_id is applied inside create(), after the
        proxy sync has already read the vals, so it used to be lost."""
        move = self.env["account.move"].create(dict(self.move_vals))
        self.assertTrue(move.invoice_user_id, "The invoice got no salesperson.")
        self.assertEqual(
            move.fiscal_document_id.user_id,
            move.invoice_user_id,
            "The invoice salesperson did not reach the fiscal document.",
        )

    def test_user_id_from_explicit_invoice_user_id(self):
        """An explicit salesperson still wins over the default."""
        move = self.env["account.move"].create(
            dict(self.move_vals, invoice_user_id=self.salesperson.id)
        )
        self.assertEqual(move.fiscal_document_id.user_id, self.salesperson)

    def test_user_id_written_after_creation(self):
        """Changing the salesperson keeps the document in sync."""
        move = self.env["account.move"].create(dict(self.move_vals))
        move.invoice_user_id = self.salesperson
        self.assertEqual(move.fiscal_document_id.user_id, self.salesperson)

    def test_user_id_when_partner_arrives_later(self):
        """Without a partner the core compute leaves the salesperson empty; it
        resolves one as soon as the partner is written, and the document has to
        follow that too."""
        vals = dict(self.move_vals)
        vals.pop("partner_id")
        move = self.env["account.move"].create(vals)
        self.assertFalse(move.invoice_user_id, "Salesperson resolved too early.")
        move.partner_id = self.partner
        self.assertTrue(move.invoice_user_id, "The invoice got no salesperson.")
        self.assertEqual(
            move.fiscal_document_id.user_id,
            move.invoice_user_id,
            "The invoice salesperson did not reach the fiscal document.",
        )

    def test_no_salesperson_stays_empty(self):
        """An invoice explicitly without a salesperson must not be given one."""
        move = self.env["account.move"].create(
            dict(self.move_vals, invoice_user_id=False)
        )
        self.assertFalse(move.invoice_user_id)
        self.assertFalse(move.fiscal_document_id.user_id)
