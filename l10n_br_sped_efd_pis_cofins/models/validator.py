# Copyright 2026 - TODAY, KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).
"""Validador estrutural do sped_base com as regras da EFD-Contribuições.

A ordem dos blocos vem do sped_base (tipo "efd_pis_cofins"). Aqui ficam as
regras próprias desta escrituração: blocos obrigatórios, bloco P proibido e
a obrigatoriedade condicional que o spec não expressa sozinho.
"""

from odoo.addons.l10n_br_sped_base.models.validator import SpedValidator

# Desde 2025 o bloco P não pode mais ser escriturado (NT 09/2024); os demais
# são obrigatórios, com ou sem dados (Guia Prático 1.35, Seção 1).
REQUIRED_BLOCKS = ["0", "A", "C", "D", "F", "I", "M", "1"]

# Guia 1.35, Registro C100: no documento cancelado (02, 03), denegado (04) ou
# inutilizado (05) só vão REG, IND_OPER, IND_EMIT, COD_MOD, COD_SIT, SER,
# NUM_DOC e CHV_NFE.
C100_KEY_FIELDS = (
    "IND_OPER",
    "IND_EMIT",
    "COD_MOD",
    "COD_SIT",
    "SER",
    "NUM_DOC",
    "CHV_NFE",
)
C100_WITHOUT_DATA = ("02", "03", "04", "05")


class EfdContribuicoesValidator(SpedValidator):
    def __init__(self, text, registers=None, kind="efd_pis_cofins"):
        super().__init__(text, registers, kind=kind)

    def _validate_blocks(self, structure):
        res = super()._validate_blocks(structure)
        codes = {code for _number, code, _fields in structure}
        if "P001" in codes:
            self._error(0, "P001", "block P is forbidden since 2025 (NT 09/2024)")
        for block in REQUIRED_BLOCKS:
            opening = "0001" if block == "0" else f"{block}001"
            closing = "0990" if block == "0" else f"{block}990"
            if opening not in codes:
                self._error(0, opening, f"the opening of block {block} is missing")
            if closing not in codes:
                self._error(0, closing, f"the closing of block {block} is missing")
        return res

    def _validate_fields(self, structure):
        if not self.registers:
            return
        for number, code, fields in structure:
            definition = self.registers.get(code)
            if definition is None:
                continue
            values = fields[1:]
            if len(values) != len(definition):
                self._error(
                    number,
                    code,
                    f"the register has {len(values)} fields and the layout "
                    f"defines {len(definition)}",
                )
                continue
            named = {
                name: value
                for value, (name, _r, _t) in zip(values, definition, strict=False)
            }
            for value, (name, required, ftype) in zip(values, definition, strict=False):
                if required and not value and self._is_required(code, name, named):
                    self._error(number, code, f"field {name} is required")
                if ftype in ("monetary", "float") and value and "." in value:
                    self._error(
                        number,
                        code,
                        f"field {name} uses a dot: the SPED decimal separator "
                        "is the comma and there is no thousands separator",
                    )

    def _is_required(self, code, name, values):
        if code == "C100" and values.get("COD_SIT") in C100_WITHOUT_DATA:
            return name in C100_KEY_FIELDS
        return True

    def _validate_specific(self, structure):
        """Referências e fechamentos que o PGE confere."""
        establishments = {f[3] for _n, c, f in structure if c == "0140"}
        participants = set()
        for _n, c, f in structure:
            if c == "0150":
                participants.add(f[1])
        for number, code, fields in structure:
            # o estabelecimento do bloco precisa estar no 0140
            # (MSG_EXISTE_CNPJ), e o participante do documento no 0150
            # (MSG_EXISTE_COD_PART)
            if code in ("A010", "C010", "D010", "F010") and (
                fields[1] not in establishments
            ):
                self._error(number, code, f"CNPJ {fields[1]} is not in a 0140")
            if code in ("A100", "C100", "D100") and fields[3]:
                if fields[3] not in participants:
                    self._error(number, code, f"COD_PART {fields[3]} is not in a 0150")
        for number, code, fields in structure:
            if code not in ("M200", "M600"):
                continue
            values = [_decimal(value) for value in fields[1:]]
            # campo 05 = 02 - 03 - 04; 08 = 05 - 06 - 07; 13 = 08 + 12
            if abs(values[3] - (values[0] - values[1] - values[2])) >= 0.01:
                self._error(number, code, "field 05 must be 02 - 03 - 04")
            if abs(values[6] - (values[3] - values[4] - values[5])) >= 0.01:
                self._error(number, code, "field 08 must be 05 - 06 - 07")
            if abs(values[11] - (values[6] + values[10])) >= 0.01:
                self._error(number, code, "field 13 must be 08 + 12")


def _decimal(value):
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0
