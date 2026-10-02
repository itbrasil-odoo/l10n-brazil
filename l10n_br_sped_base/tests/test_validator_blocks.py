# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from odoo.tests import common

from odoo.addons.l10n_br_sped_base.models.validator import SpedValidator

TEXT = "\n".join(
    [
        "|0000|x|",
        "|0001|0|",
        "|0990|2|",
        "|C001|1|",
        "|C990|2|",
        "|E001|1|",
        "|E990|2|",
        "|9001|0|",
        "|9990|2|",
        "|9999|9|",
    ]
)


class TestValidatorBlocks(common.TransactionCase):
    def test_each_declaration_declares_its_block_order(self):
        # the default order (ECF/ECD) has no block C: C before E is "out of
        # order" there, and the right order for the EFD ICMS/IPI
        default = SpedValidator(TEXT).validate()
        self.assertTrue(any("out of the official order" in str(i) for i in default))

        class EfdValidator(SpedValidator):
            blocks = ["0", "B", "C", "D", "E", "G", "H", "K", "1"]

        issues = EfdValidator(TEXT).validate()
        self.assertFalse(
            [i for i in issues if "order" in str(i)], [str(i) for i in issues]
        )
