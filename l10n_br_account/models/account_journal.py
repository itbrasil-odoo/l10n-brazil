# Copyright 2023 Akretion (Raphaẽl Valyi <raphael.valyi@akretion.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import base64

from odoo import models

XML_MIMETYPES = ("text/xml", "application/xml")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _is_fiscal_xml_attachment(self, attachment):
        """Whether the attachment looks like an XML the fiscal importer can read.

        Browsers are inconsistent about the mimetype they send for .xml files
        (text/xml, application/xml, sometimes text/plain or a generic octet
        stream), so fall back to the file name and finally to sniffing the
        first bytes of the payload.
        """
        if attachment.mimetype in XML_MIMETYPES:
            return True
        if (attachment.name or "").lower().endswith(".xml"):
            return True
        try:
            head = base64.b64decode(attachment.datas or b"")[:512].lstrip()
        except Exception:
            return False
        return head.startswith(b"<?xml") or head.startswith(b"<")

    def create_document_from_attachment(self, attachment_ids=None):
        if self.env.company.country_id.code != "BR" or len(attachment_ids or []) < 1:
            return super().create_document_from_attachment(
                attachment_ids=attachment_ids
            )
        attachments = self.env["ir.attachment"].browse(attachment_ids)
        xml_attachments = attachments.filtered(self._is_fiscal_xml_attachment)
        if not xml_attachments:
            # Nothing to parse as a fiscal XML: hand the files back to the
            # standard Odoo flow, which knows how to deal with PDFs and the
            # like. Without this, ANY file dropped on the journal reached
            # _parse_file_data() -> XmlParser().from_bytes(), which raises a
            # raw xsdata.exceptions.ParserError ("Failed to create target
            # class ''") straight to the user. Seen in production with a
            # 500 KB image.jpg dropped on the customer invoices journal.
            return super().create_document_from_attachment(
                attachment_ids=attachment_ids
            )
        # Mixed batch: the XMLs drive the fiscal import; _get_importer_action
        # reassigns res_model/res_id of what it receives, so the non-XML files
        # are deliberately left out of it and keep their current link.
        return self.env["l10n_br_fiscal.document.import.wizard"]._get_importer_action(
            xml_attachments
        )
