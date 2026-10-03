# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Rules of layout 020 and of the 2026 tax reform (Guia Prático 3.2.4).

Every document here is fictitious: made-up partners, numbers and keys.
"""

from io import StringIO

from odoo.tests import common, tagged

from odoo.addons.l10n_br_sped_efd_icms_ipi.models.sped_efd_icms_ipi import (
    cod_sit,
    icms_document_totals,
    import_document_code,
)


def fake_key(number):
    """A well-formed NF-e key of a fictitious issuer (11.222.333/0001-81)."""
    base = f"3126091122233300018155001{number:09d}1{number:08d}"
    weights = [2, 3, 4, 5, 6, 7, 8, 9]
    total = sum(int(digit) * weights[i % 8] for i, digit in enumerate(reversed(base)))
    rest = total % 11
    return base + str(0 if rest < 2 else 11 - rest)


# Alphanumeric CNPJ as published by the RFB for the 2026 layout (fictitious).
ALNUM_CNPJ = "12.ABC.345/01DE-35"
ALNUM_CNPJ_STRIPPED = "12ABC34501DE35"


class Rules2026Common(common.TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.env.user.tz = "America/Sao_Paulo"
        cls.company = cls.env.company
        # the ST and DIFAL registers are keyed by the UF of the company: a
        # database without demo data has none, so the tests set it
        if not cls.company.state_id:
            cls.company.state_id = cls.env.ref("base.state_br_mg")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Ficticio Alfanumerico",
                "is_company": True,
                "vat": ALNUM_CNPJ,
                "country_id": cls.env.ref("base.br").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Peca ficticia", "default_code": "FIC-001"}
        )
        cls.declaration = cls.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": cls.company.id,
                "DT_INI": "2026-09-01",
                "DT_FIN": "2026-09-30",
            }
        )
        cls.cbs_group = cls.env.ref("l10n_br_fiscal.tax_group_cbs")
        cls.ibs_group = cls.env.ref("l10n_br_fiscal.tax_group_ibs")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _document(self, number, state_edoc="autorizada", lines=None, **vals):
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": self.company.id,
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": str(number),
                "document_serie": "1",
                "partner_id": self.partner.id,
                "fiscal_operation_type": "out",
                "issuer": "company",
                # the document totals are only computed under an operation
                "fiscal_operation_id": self.env.ref(
                    "l10n_br_fiscal.fo_compras"
                    if vals.get("fiscal_operation_type") == "in"
                    else "l10n_br_fiscal.fo_venda"
                ).id,
                # 30/09 21:30 in Brasilia is already 01/10 in UTC: the period
                # bounds and DT_DOC have to read it as September.
                "document_date": "2026-10-01 00:30:00",
                "document_key": fake_key(number),
                **vals,
            }
        )
        for line_vals in lines or [{}]:
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "name": "Item ficticio",
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100.0,
                    **line_vals,
                }
            )
        # set after the lines: the state is not what this test is about, the
        # SPED reading of it is
        document.write({"state_edoc": state_edoc})
        return document

    def _icms_line(self, **vals):
        return {
            "icms_tax_id": self.env.ref("l10n_br_fiscal.tax_icms_18").id,
            "icms_cst_id": self.env.ref("l10n_br_fiscal.cst_icms_60").id,
            **vals,
        }

    def _reform_line(self, **vals):
        return {
            "cbs_tax_id": self.env.ref("l10n_br_fiscal.tax_cbs_0_9").id,
            "cbs_cst_id": self.env.ref("l10n_br_fiscal.cst_cbs_000").id,
            "cbs_value": 0.90,
            "ibs_tax_id": self.env.ref("l10n_br_fiscal.tax_ibs_0_1").id,
            "ibs_cst_id": self.env.ref("l10n_br_fiscal.cst_ibs_000").id,
            "ibs_value": 0.10,
            **vals,
        }

    def _pull_c100(self):
        model = self.env["l10n_br_sped.efd_icms_ipi.c100"].with_context(
            company_id=self.company.id,
            declaration=self.declaration,
            default_declaration_id=self.declaration.id,
        )
        self.declaration.invalidate_recordset()
        model._pull_records_from_odoo("efd_icms_ipi", 2, log_msg=StringIO())
        return self.env["l10n_br_sped.efd_icms_ipi.c100"].search(
            [("declaration_id", "=", self.declaration.id)]
        )

    def _c100_of(self, document):
        return self._pull_c100().filtered(
            lambda reg: reg.res_model == "l10n_br_fiscal.document"
            and reg.res_id == document.id
        )


@tagged("post_install", "-at_install")
class TestRules2026(Rules2026Common):
    # ------------------------------------------------------------------
    # COD_SIT with state_fiscal NULL
    # ------------------------------------------------------------------

    def test_cod_sit_derived_when_state_fiscal_is_empty(self):
        cases = {
            "autorizada": "00",
            "cancelada": "02",
            "denegada": "04",
            "inutilizada": "05",
        }
        for number, (state_edoc, expected) in enumerate(cases.items(), start=1):
            with self.subTest(state_edoc=state_edoc):
                document = self._document(number, state_edoc=state_edoc)
                document.state_fiscal = False
                self.assertEqual(cod_sit(document), expected)

    def test_cod_sit_complementary_nfe(self):
        document = self._document(10)
        # the purpose follows the operation; a complementary NF-e sets it
        document.edoc_purpose = "2"
        document.state_fiscal = False
        self.assertEqual(cod_sit(document), "06")

    def test_state_fiscal_wins_when_it_is_a_code_of_the_table(self):
        document = self._document(11)
        document.state_fiscal = "01"
        self.assertEqual(cod_sit(document), "01")

    def test_c100_never_goes_out_with_empty_cod_sit(self):
        document = self._document(12, lines=[self._icms_line()])
        document.state_fiscal = False
        self.assertEqual(self._c100_of(document).COD_SIT, "00")

    def test_cancelled_c100_carries_only_the_identification(self):
        """Guia Prático, C100, Exceção 1: no values and no child register."""
        document = self._document(13, state_edoc="cancelada")
        document.state_fiscal = False
        c100 = self._c100_of(document)
        self.assertEqual(c100.COD_SIT, "02")
        self.assertEqual(c100.CHV_NFE, document.document_key)
        self.assertFalse(c100.COD_PART)
        self.assertFalse(c100.VL_DOC)
        self.assertFalse(c100.DT_DOC)
        self.assertFalse(c100.reg_C190_ids)

    # ------------------------------------------------------------------
    # Seção 10: CBS, IBS and IS outside VL_DOC and VL_OPR
    # ------------------------------------------------------------------

    def test_vl_doc_and_vl_opr_leave_cbs_ibs_out(self):
        # the worst case: CBS/IBS configured as ADDED to the total
        (self.cbs_group | self.ibs_group).write({"tax_include": False})
        document = self._document(20, lines=[self._icms_line(**self._reform_line())])
        document.fiscal_line_ids._compute_fiscal_amounts()
        line = document.fiscal_line_ids
        total_with_reform = line.fiscal_amount_total
        c100 = self._c100_of(document)
        expected = total_with_reform - line.cbs_value - line.ibs_value
        self.assertAlmostEqual(c100.VL_DOC, expected, places=2)
        self.assertAlmostEqual(sum(c100.reg_C190_ids.mapped("VL_OPR")), expected, 2)

    def test_included_cbs_ibs_are_not_subtracted_twice(self):
        (self.cbs_group | self.ibs_group).write({"tax_include": True})
        document = self._document(21, lines=[self._icms_line(**self._reform_line())])
        line = document.fiscal_line_ids
        c100 = self._c100_of(document)
        self.assertAlmostEqual(c100.VL_DOC, line.fiscal_amount_total, places=2)

    def test_document_with_only_reform_taxes_is_not_bookkept(self):
        only_new = self._document(22, lines=[self._reform_line()])
        with_icms = self._document(23, lines=[self._icms_line(**self._reform_line())])
        pulled = self._pull_c100()
        self.assertNotIn(only_new.id, pulled.mapped("res_id"))
        self.assertIn(with_icms.id, pulled.mapped("res_id"))

    # ------------------------------------------------------------------
    # dates in the local calendar
    # ------------------------------------------------------------------

    def test_last_evening_of_the_month_is_in_the_period(self):
        document = self._document(30, lines=[self._icms_line()])
        c100 = self._c100_of(document)
        self.assertTrue(c100, "the 30th at 21:30 (BRT) belongs to September")
        self.assertEqual(str(c100.DT_DOC), "2026-09-30")

    # ------------------------------------------------------------------
    # layout 020: CNPJ and key as text
    # ------------------------------------------------------------------

    def test_alphanumeric_cnpj_goes_out_as_text(self):
        document = self._document(40, lines=[self._icms_line()])
        c100 = self._c100_of(document)
        self.assertEqual(c100.COD_PART, ALNUM_CNPJ_STRIPPED)
        vals = self.env["l10n_br_sped.efd_icms_ipi.0150"]._map_from_odoo(
            self.partner, None, self.declaration
        )
        self.assertEqual(vals["CNPJ"], ALNUM_CNPJ_STRIPPED)
        self.assertEqual(vals["COD_PART"], ALNUM_CNPJ_STRIPPED)
        # the key goes out as written, never coerced to a number
        self.assertEqual(c100.CHV_NFE, document.document_key)
        for name in ("CNPJ",):
            self.assertEqual(
                self.env["l10n_br_sped.efd_icms_ipi.0150"]._fields[name].type, "char"
            )
        self.assertEqual(
            self.env["l10n_br_sped.efd_icms_ipi.c100"]._fields["CHV_NFE"].type,
            "char",
        )

    # ------------------------------------------------------------------
    # layout 020: C120.COD_DOC_IMP = 2 for the DUIMP
    # ------------------------------------------------------------------

    def test_duimp_is_import_document_2(self):
        self.assertEqual(import_document_code("26BR00012345678"), "2")
        self.assertEqual(import_document_code("2612345678"), "0")
        self.assertEqual(import_document_code(""), "0")

    def test_c120_from_the_nfe_import_declaration(self):
        if "nfe.40.di" not in self.env:
            self.skipTest("l10n_br_nfe is not installed: no <DI> to read")
        document = self._document(
            50, lines=[self._icms_line()], fiscal_operation_type="in"
        )
        self.env["nfe.40.di"].create(
            {
                "nfe40_DI_prod_id": document.fiscal_line_ids.id,
                "nfe40_nDI": "26BR00012345678",
            }
        )
        c120 = self._c100_of(document).reg_C120_ids
        self.assertEqual(len(c120), 1)
        self.assertEqual(c120.COD_DOC_IMP, "2")
        self.assertEqual(c120.NUM_DOC_IMP, "26BR00012345678")

    # ------------------------------------------------------------------
    # layout 020: 1310.CAP_TANQUE
    # ------------------------------------------------------------------

    def test_1310_carries_cap_tanque_as_field_11(self):
        model = self.env["l10n_br_sped.efd_icms_ipi.1310"]
        self.assertIn("CAP_TANQUE", model._fields)
        names = [
            name
            for name, field in model._fields.items()
            if name.isupper() and field.type not in ("one2many", "many2one")
        ]
        # field 01 is REG, written by the base: CAP_TANQUE is the 10th data
        # field, i.e. field 11 of the register
        self.assertEqual(names[-1], "CAP_TANQUE")
        self.assertEqual(len(names), 10)

    # ------------------------------------------------------------------
    # formatting
    # ------------------------------------------------------------------

    def test_monetary_uses_the_comma(self):
        model = self.env["l10n_br_sped.efd_icms_ipi.c190"]
        field = model._fields["VL_OPR"]
        self.assertEqual(model._format_field_value(field, 1234.5), "1234,50")
        self.assertEqual(model._format_field_value(field, 1234.0), "1234")
        self.assertEqual(model._format_field_value(field, 0.0), "0")


@tagged("post_install", "-at_install")
class TestPvaRules(Rules2026Common):
    """Rules the PVA 6.1.1 refused on a real file, one test each."""

    def _pull(self, model_name):
        model = self.env[model_name].with_context(
            company_id=self.company.id,
            declaration=self.declaration,
            default_declaration_id=self.declaration.id,
        )
        self.declaration.invalidate_recordset()
        model._pull_records_from_odoo("efd_icms_ipi", 2, log_msg=StringIO())
        return self.env[model_name].search(
            [("declaration_id", "=", self.declaration.id)]
        )

    def test_entry_takes_the_ipi_cst_of_the_entry_side(self):
        # a supplier's NF-e brings its exit CST (50); the entry books 00
        document = self._document(
            60,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_2152").id,
                    ipi_cst_id=self.env.ref("l10n_br_fiscal.cst_ipi_50").id,
                )
            ],
        )
        c170 = self._c100_of(document).reg_C170_ids
        self.assertEqual(c170.CST_IPI, "00")
        self.assertFalse(c170.COD_ENQ, "the framework code is the issuer's")
        self.assertEqual(c170.COD_ITEM, "FIC-001")

    def test_own_nfe_has_no_items_and_no_0200(self):
        """Exceção 2, and the PVA refuses a 0200 no register references."""
        document = self._document(61, lines=[self._icms_line()])
        self.assertFalse(self._c100_of(document).reg_C170_ids)
        self.assertFalse(self._pull("l10n_br_sped.efd_icms_ipi.0200"))

    def test_participant_of_a_cancelled_document_is_not_listed(self):
        cancelled_partner = self.partner.copy({"vat": False, "name": "Cancelado"})
        self._document(62, state_edoc="cancelada", partner_id=cancelled_partner.id)
        self._document(63, lines=[self._icms_line()])
        partners = self._pull("l10n_br_sped.efd_icms_ipi.0150").mapped("res_id")
        self.assertIn(self.partner.id, partners)
        self.assertNotIn(cancelled_partner.id, partners)

    def test_foreign_participant_gets_a_code(self):
        foreign = self.env["res.partner"].create(
            {"name": "Fornecedor estrangeiro", "country_id": self.env.ref("base.us").id}
        )
        vals = self.env["l10n_br_sped.efd_icms_ipi.0150"]._map_from_odoo(
            foreign, None, self.declaration
        )
        self.assertEqual(vals["COD_PART"], f"P{foreign.id}")

    def test_c101_only_for_another_uf(self):
        self.partner.state_id = self.company.state_id
        same_uf = self._document(64, lines=[self._icms_line()])
        same_uf.amount_icmsfcp_value = 10.0
        self.assertFalse(self._c100_of(same_uf).reg_C101_ids)

    def test_st_retention_feeds_e200_e210(self):
        self.partner.state_id = self.company.state_id
        self._document(
            65,
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_5405").id,
                    icmsst_value=12.34,
                )
            ],
        )
        self.declaration.write({"cod_receita": "1206", "cod_receita_st": "2204"})
        e200 = self._pull("l10n_br_sped.efd_icms_ipi.e200")
        self.assertEqual(e200.mapped("UF"), [self.company.state_id.code])
        e210 = e200.reg_E210_ids
        self.assertAlmostEqual(e210.VL_RETENCAO_ST, 12.34, places=2)
        self.assertAlmostEqual(e210.VL_ICMS_RECOL_ST, 12.34, places=2)
        self.assertEqual(e210.IND_MOV_ST, "1")
        # the ST obligation carries the ST revenue code, not the own ICMS one
        self.assertEqual(e210.reg_E250_ids.COD_REC, "2204")
        self.assertEqual(e210.reg_E250_ids.COD_OR, "002")

    def test_no_e500_for_who_is_not_an_ipi_taxpayer(self):
        group = self.env["account.tax.group"].create(
            {
                "name": "IPI (teste)",
                "fiscal_tax_group_id": self.env.ref("l10n_br_fiscal.tax_group_ipi").id,
            }
        )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": "2026-09-01",
                "date_to": "2026-09-30",
            }
        )
        assessment.state = "posted"
        self.declaration.IND_ATIV = "1"
        self.assertFalse(self._pull("l10n_br_sped.efd_icms_ipi.e500"))
        self.declaration.IND_ATIV = "0"
        self.assertTrue(self._pull("l10n_br_sped.efd_icms_ipi.e500"))

    def test_csosn_of_a_simples_supplier_becomes_the_declarant_cst(self):
        csosn = self.env["l10n_br_fiscal.cst"].search([("code", "=", "500")], limit=1)
        if not csosn:
            self.skipTest("no CSOSN 500 in the CST table")
        document = self._document(
            66,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[
                {
                    "cfop_id": self.env.ref("l10n_br_fiscal.cfop_2152").id,
                    "icms_cst_id": csosn.id,
                    "icms_origin": "0",
                }
            ],
        )
        c100 = self._c100_of(document)
        self.assertEqual(c100.reg_C170_ids.CST_ICMS, "060")
        self.assertEqual(c100.reg_C190_ids.CST_ICMS, "060")

    def test_difal_to_another_uf_feeds_e300_e310(self):
        other_uf = self.env["res.country.state"].search(
            [
                ("country_id", "=", self.env.ref("base.br").id),
                ("id", "!=", self.company.state_id.id),
            ],
            limit=1,
        )
        self.partner.state_id = other_uf
        document = self._document(
            67,
            lines=[self._icms_line(icms_destination_value=7.5, icmsfcp_value=1.5)],
        )
        c101 = self._c100_of(document).reg_C101_ids
        self.assertAlmostEqual(c101.VL_ICMS_UF_DEST, 7.5, places=2)
        e300 = self._pull("l10n_br_sped.efd_icms_ipi.e300")
        self.assertEqual(e300.mapped("UF"), [other_uf.code])
        e310 = e300.reg_E310_ids
        self.assertAlmostEqual(e310.VL_TOT_DEBITOS_DIFAL, 7.5, places=2)
        self.assertAlmostEqual(e310.VL_RECOL_FCP, 1.5, places=2)
        self.assertEqual(sorted(e310.reg_E316_ids.mapped("COD_OR")), ["000", "006"])

    def test_entry_belongs_to_the_period_of_its_entry_date(self):
        received_later = self._document(
            68,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[self._icms_line()],
            date_in_out="2026-10-05 12:00:00",
        )
        received_now = self._document(
            69,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[self._icms_line()],
            document_date="2026-08-28 12:00:00",
            date_in_out="2026-09-02 12:00:00",
        )
        pulled = self._pull_c100().mapped("res_id")
        self.assertNotIn(received_later.id, pulled)
        self.assertIn(received_now.id, pulled)

    def test_exit_after_the_period_leaves_dt_e_s_empty(self):
        document = self._document(
            70, lines=[self._icms_line()], date_in_out="2026-10-03 12:00:00"
        )
        self.assertFalse(self._c100_of(document).DT_E_S)

    def test_header_cod_ver_and_profile(self):
        """COD_VER has three positions; the profile is the declaration's."""
        self.assertEqual(self.declaration.IND_PERFIL, "B", "default profile")
        self.declaration.IND_PERFIL = "A"
        vals = self.declaration._map_from_odoo(self.company, None, self.declaration)
        self.assertEqual(vals["COD_VER"], "020")
        self.assertNotIn("IND_PERFIL", vals, "the pull must not overwrite it")

    def test_0002_only_for_industry(self):
        self.declaration.IND_ATIV = "1"
        self.assertFalse(self._pull("l10n_br_sped.efd_icms_ipi.0002"))
        self.declaration.IND_ATIV = "0"
        self.assertTrue(self._pull("l10n_br_sped.efd_icms_ipi.0002"))

    def test_cest_and_ncm_without_mask(self):
        ncm = self.env["l10n_br_fiscal.ncm"].search([("code", "like", ".")], limit=1)
        cest = self.env["l10n_br_fiscal.cest"].search([("code", "like", ".")], limit=1)
        if not (ncm and cest):
            self.skipTest("no masked NCM/CEST in the tables")
        self.product.write({"ncm_id": ncm.id, "cest_id": cest.id})
        vals = self.env["l10n_br_sped.efd_icms_ipi.0200"]._map_from_odoo(
            self.product, None, self.declaration
        )
        self.assertNotIn(".", vals["COD_NCM"])
        self.assertNotIn(".", vals["CEST"])

    def test_0220_for_a_c170_unit_other_than_the_inventory_one(self):
        unit = self.env.ref("uom.product_uom_unit")
        dozen = self.env.ref("uom.product_uom_dozen")
        unit.code = unit.code or "UN"
        dozen.code = dozen.code or "DZ"
        self.product.uom_id = unit
        self._document(
            71,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[self._icms_line(uom_id=dozen.id)],
        )
        reg_0200 = self._pull("l10n_br_sped.efd_icms_ipi.0200")
        reg_0220 = reg_0200.reg_0220_ids
        self.assertEqual(reg_0220.UNID_CONV, dozen.code)
        self.assertAlmostEqual(reg_0220.FAT_CONV, 12.0, places=4)

    def test_denied_and_voided_are_not_bookkept(self):
        """Codes 04/05 of Tabela 4.1.2 were discontinued in January 2023."""
        denied = self._document(72, state_edoc="denegada")
        voided = self._document(73, state_edoc="inutilizada")
        pulled = self._pull_c100().mapped("res_id")
        self.assertNotIn(denied.id, pulled)
        self.assertNotIn(voided.id, pulled)

    def test_one_0150_per_participant_code(self):
        twin = self.partner.copy({"name": "Mesmo CNPJ, outro cadastro"})
        # the uniqueness check is newer than the data: real databases have
        # such twins (archived or imported), so the test plants one in SQL
        self.env.cr.execute(
            "UPDATE res_partner SET vat = %s, cnpj_cpf_stripped = %s WHERE id = %s",
            (self.partner.vat, self.partner.cnpj_cpf_stripped, twin.id),
        )
        twin.invalidate_recordset()
        self._document(74, lines=[self._icms_line()])
        self._document(75, lines=[self._icms_line()], partner_id=twin.id)
        codes = self._pull("l10n_br_sped.efd_icms_ipi.0150").mapped("COD_PART")
        self.assertEqual(len(codes), len(set(codes)))

    def test_base_reduction_goes_to_vl_red_bc(self):
        cst20 = self.env.ref("l10n_br_fiscal.cst_icms_20")
        document = self._document(
            76,
            lines=[self._icms_line(icms_cst_id=cst20.id, icms_base=60.0)],
        )
        c190 = self._c100_of(document).reg_C190_ids
        self.assertAlmostEqual(c190.VL_RED_BC, c190.VL_OPR - 60.0, places=2)
        self.assertGreater(c190.VL_RED_BC, 0)

    def test_icms_document_totals_follow_the_c190(self):
        """E110 campos 02 e 06: ICMS das saídas e das entradas pelo CFOP.

        Nota cancelada não soma, porque também não tem C190.
        """
        self.partner.state_id = self.company.state_id
        self._document(
            70,
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_5102").id,
                    icms_value=18.0,
                )
            ],
        )
        self._document(
            71,
            fiscal_operation_type="in",
            issuer="partner",
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_1102").id,
                    icms_value=7.0,
                )
            ],
        )
        self._document(
            72,
            state_edoc="cancelada",
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_5102").id,
                    icms_value=99.0,
                )
            ],
        )
        # 5605 (transferência de saldo devedor) conta como crédito
        self._document(
            73,
            lines=[
                self._icms_line(
                    cfop_id=self.env.ref("l10n_br_fiscal.cfop_5605").id,
                    icms_value=3.0,
                )
            ],
        )
        totals = icms_document_totals(self.env, self.declaration)
        self.assertAlmostEqual(totals["debit"], 18.0, places=2)
        self.assertAlmostEqual(totals["credit"], 10.0, places=2)

    def test_entry_whose_bill_was_cancelled_is_not_bookkept(self):
        """A loja cancela a fatura de entrada e relança a mesma NF-e.

        O documento da fatura cancelada continua "autorizada" (é NF-e de
        terceiro), às vezes sem número: não pode virar C100.
        """
        if "move_ids" not in self.env["l10n_br_fiscal.document"]._fields:
            self.skipTest("l10n_br_account is not installed")
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        if not journal:
            self.skipTest("no purchase journal in this database")
        withdrawn = self._document(
            80,
            fiscal_operation_type="in",
            issuer="partner",
            document_number=False,
            document_key=False,
            lines=[self._icms_line()],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "journal_id": journal.id,
                "partner_id": self.partner.id,
            }
        )
        move.fiscal_document_id = withdrawn
        self.assertIn(move, withdrawn.move_ids)
        move.button_cancel()
        withdrawn.write({"state_edoc": "autorizada"})
        relaunched = self._document(
            81, fiscal_operation_type="in", issuer="partner", lines=[self._icms_line()]
        )
        self.declaration.invalidate_recordset()
        domain = self.env["l10n_br_sped.efd_icms_ipi.c100"]._odoo_domain(
            None, self.declaration
        )
        ids = self.env["l10n_br_fiscal.document"].search(domain).ids
        self.assertNotIn(withdrawn.id, ids)
        self.assertIn(relaunched.id, ids)
