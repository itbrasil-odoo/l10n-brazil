# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).
"""Structural validator of the sped_base with the EFD ICMS/IPI rules."""

from odoo.addons.l10n_br_sped_base.models.sped_mixin import LAYOUT_VERSIONS
from odoo.addons.l10n_br_sped_base.models.validator import SpedValidator

from .sped_efd_icms_ipi import COD_SIT_WITHOUT_VALUES

# Guia Prático 3.2.4, Capítulo II, Seção 1 (Tabela Blocos)
EFD_ICMS_IPI_BLOCKS = ["0", "B", "C", "D", "E", "G", "H", "K", "1"]


class EfdIcmsIpiValidator(SpedValidator):
    blocks = EFD_ICMS_IPI_BLOCKS

    def _validate_fields(self, structure):
        """A cancelled, denied or voided C100 carries only its identification.

        Guia Prático, C100, Exceção 1: every other field is empty, so the
        generic requiredness does not apply to it; the field count still does.
        """

        def without_values(entry):
            _number, code, fields = entry
            return (
                code == "C100"
                # fields[0] is REG: COD_SIT, field 06, is at index 5
                and len(fields) > 5
                and fields[5] in COD_SIT_WITHOUT_VALUES
            )

        super()._validate_fields([e for e in structure if not without_values(e)])
        definition = self.registers.get("C100")
        if not definition:
            return
        for number, code, fields in filter(without_values, structure):
            if len(fields) - 1 != len(definition):
                self._error(
                    number,
                    code,
                    f"the register has {len(fields) - 1} fields and the layout "
                    f"defines {len(definition)}",
                )


def efd_icms_ipi_registers(env, version=None):
    """``{code: [(field, required, type)]}`` from the layout spec models."""
    version = version or LAYOUT_VERSIONS["efd_icms_ipi"]
    prefix = f"l10n_br_sped.efd_icms_ipi.{version}."
    registers = {}
    for name in env.registry:
        if not name.startswith(prefix):
            continue
        definition = []
        for fname, field in env[name]._fields.items():
            if not fname.isupper() or field.type in (
                "one2many",
                "many2one",
                "many2many",
            ):
                continue
            required = bool(getattr(field, "in_required", False))
            definition.append((fname, required, field.type))
        registers[name.rsplit(".", 1)[1].upper()] = definition
    return registers


def validate_efd_icms_ipi(env, text):
    """Issues the structural validator finds in an EFD ICMS/IPI text."""
    return EfdIcmsIpiValidator(text, efd_icms_ipi_registers(env)).validate()
