# Copyright (C) 2026 - Renan Teixeira
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from ..constants.fiscal import (
    COMMENT_TYPE_FISCAL,
    FISCAL_COMMENT_DOCUMENT,
    FISCAL_COMMENT_LINE,
)


class TestComment(TransactionCase):
    """The Test Message button of l10n_br_fiscal.comment.

    Its reference field used to offer only the abstract document mixins, so it
    could never be filled and every template using ``doc`` failed with a Jinja
    UndefinedError instead of a rendered message.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": "123",
            }
        )
        cls.document.user_id = cls.env.user
        cls.line = cls.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": cls.document.id,
                "name": "Comment fixture line",
                "quantity": 1,
                "price_unit": 10,
            }
        )

    def _new_comment(self, comment, object=FISCAL_COMMENT_DOCUMENT):
        return self.env["l10n_br_fiscal.comment"].create(
            {
                "name": "Test Comment",
                "comment": comment,
                "comment_type": COMMENT_TYPE_FISCAL,
                "object": object,
            }
        )

    def test_object_id_offers_only_browsable_models(self):
        """The reference must point to models that actually have records."""
        selection = (
            self.env["l10n_br_fiscal.comment"]._fields["object_id"].get_values(self.env)
        )
        self.assertTrue(selection, "No model offered as test reference.")
        for model_name in selection:
            self.assertFalse(
                self.env[model_name]._abstract,
                f"{model_name} is abstract, so no record can ever be selected.",
            )

    def test_test_message_without_reference(self):
        """An empty reference is a user mistake, not a traceback."""
        comment = self._new_comment("Issued by: ${doc.user_id.name}")
        with self.assertRaises(UserError):
            comment.action_test_message()

    def test_test_message_with_document(self):
        """A document reference renders the same ``doc`` the emission does."""
        comment = self._new_comment("Issued by: ${doc.user_id.name}")
        comment.object_id = self.document
        comment.action_test_message()
        self.assertEqual(comment.test_comment, f"Issued by: {self.env.user.name}")

    def test_test_message_with_document_line(self):
        """A line reference gets ``item``, and ``doc`` is the line's document,
        just like l10n_br_fiscal.document.line._document_comment does."""
        comment = self._new_comment(
            "${item.name} / ${doc.document_number}", object=FISCAL_COMMENT_LINE
        )
        comment.object_id = self.line
        comment.action_test_message()
        self.assertEqual(
            comment.test_comment,
            f"{self.line.name} / {self.document.document_number}",
        )
