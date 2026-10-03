# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import BaseCase

from ..models.validator import SpedValidator


def _file(*registers):
    """SPED text with blocks 9 and 9999 counted from the given registers."""
    lines = list(registers)
    codes = [line.split("|")[1] for line in lines] + ["9001", "9990", "9999"]
    counts = {}
    for code in codes:
        counts[code] = counts.get(code, 0) + 1
    block9 = ["|9001|0|"] + [f"|9900|{c}|{n}|" for c, n in counts.items()]
    block9.append(f"|9900|9900|{len(counts) + 1}|")
    block9 += [f"|9990|{len(block9) + 2}|"]
    total = len(lines) + len(block9) + 1
    return "\n".join(lines + block9 + [f"|9999|{total}|"])


class TestValidatorBlockOrder(BaseCase):
    def _blocks_errors(self, text, kind):
        issues = SpedValidator(text, kind=kind).validate()
        return [i for i in issues if "order" in i.message or "reappears" in i.message]

    def test_order_follows_the_kind(self):
        contrib = _file(
            "|0000|006|",
            "|0001|0|",
            "|0990|3|",
            "|A001|1|",
            "|A990|2|",
            "|M001|1|",
            "|M990|2|",
            "|1001|1|",
            "|1990|2|",
        )
        # EFD-Contribuições: 0, A, ..., M, ..., 1, 9 is the official order
        self.assertFalse(self._blocks_errors(contrib, "efd_pis_cofins"))
        # with the ECF order the same file is refused: block A does not exist
        self.assertTrue(self._blocks_errors(contrib, "ecf"))

    def test_out_of_order_is_reported(self):
        icms = _file(
            "|0000|020|",
            "|0001|0|",
            "|0990|3|",
            "|E001|1|",
            "|E990|2|",
            "|C001|1|",
            "|C990|2|",
        )
        self.assertTrue(self._blocks_errors(icms, "efd_icms_ipi"))

    def test_default_kind_is_ecf(self):
        self.assertEqual(SpedValidator("").blocks[1], "E")
