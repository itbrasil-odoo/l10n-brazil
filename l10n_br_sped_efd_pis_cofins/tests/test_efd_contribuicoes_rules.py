# Copyright 2026 - TODAY, KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).
"""Regras do leiaute 006 e de 2026, com dados fictícios."""

from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models.sped_efd_pis_cofins import _cod_mod


def _cnpj(root, branch):
    """CNPJ fictício com dígitos verificadores válidos."""
    base = f"{root:08d}{branch:04d}"
    for weights in (
        [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
        [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
    ):
        total = sum(int(d) * w for d, w in zip(base, weights, strict=True))
        digit = 11 - total % 11
        base += str(0 if digit >= 10 else digit)
    return base


@tagged("post_install", "-at_install")
class TestEfdContribuicoesRules(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        ref = cls.env.ref
        state = ref("base.state_br_mg")
        city = ref("l10n_br_base.city_3106200")
        cls.matriz = cls.env["res.company"].create(
            {
                "name": "Autopeças Fictícia Matriz",
                "legal_name": "AUTOPECAS FICTICIA LTDA",
                "vat": _cnpj(60708091, 1),
                "country_id": ref("base.br").id,
                "state_id": state.id,
                "city_id": city.id,
                "currency_id": ref("base.BRL").id,
                "profit_calculation": "real",
            }
        )
        cls.filial = cls.env["res.company"].create(
            {
                "name": "Autopeças Fictícia Filial",
                "legal_name": "AUTOPECAS FICTICIA LTDA",
                "vat": _cnpj(60708091, 2),
                "country_id": ref("base.br").id,
                "state_id": state.id,
                "city_id": city.id,
                "parent_id": cls.matriz.id,
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Cliente Fictício",
                "is_company": True,
                "vat": _cnpj(70809012, 1),
                "country_id": ref("base.br").id,
                "state_id": state.id,
                "city_id": city.id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Pastilha de freio fictícia",
                "default_code": "PF-01",
                "ncm_id": ref("l10n_br_fiscal.ncm_94033000").id,
                "fiscal_type": "00",
            }
        )
        cls.doc_55 = ref("l10n_br_fiscal.document_55")
        cls.fo_venda = ref("l10n_br_fiscal.fo_venda")
        cls.cfop_venda = ref("l10n_br_fiscal.cfop_5102")
        cls.cfop_transf = ref("l10n_br_fiscal.cfop_5152")
        cls.cst_pis_01 = ref("l10n_br_fiscal.cst_pis_01")
        cls.cst_pis_04 = ref("l10n_br_fiscal.cst_pis_04")
        cls.cst_cofins_01 = ref("l10n_br_fiscal.cst_cofins_01")
        cls.cst_cofins_04 = ref("l10n_br_fiscal.cst_cofins_04")
        cls.number = 100

    def _document(
        self,
        company=None,
        lines=None,
        state="autorizada",
        day=10,
        operation=None,
        issuer="company",
    ):
        """Documento de venda autorizado, com tributos já calculados.

        `imported_document` preserva os valores informados nas linhas, como
        numa nota importada por XML.
        """
        self.__class__.number += 1
        lines = lines or [{}]
        line_vals = []
        for extra in lines:
            vals = {
                "name": self.product.name,
                "product_id": self.product.id,
                "uom_id": self.product.uom_id.id,
                "quantity": 1.0,
                "price_unit": 100.0,
                "fiscal_price": 100.0,
                "fiscal_quantity": 1.0,
                "cfop_id": self.cfop_venda.id,
                "fiscal_operation_id": (operation or self.fo_venda).id,
                "pis_cst_id": self.cst_pis_01.id,
                "pis_base": 100.0,
                "pis_percent": 1.65,
                "pis_value": 1.65,
                "cofins_cst_id": self.cst_cofins_01.id,
                "cofins_base": 100.0,
                "cofins_percent": 7.6,
                "cofins_value": 7.6,
            }
            vals.update(extra)
            line_vals.append((0, 0, vals))
        return self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": (company or self.matriz).id,
                "partner_id": self.customer.id,
                "document_type_id": self.doc_55.id,
                "fiscal_operation_id": (operation or self.fo_venda).id,
                "issuer": issuer,
                "imported_document": True,
                "document_number": str(self.number),
                "document_serie": "1",
                "document_date": datetime(2026, 9, day, 15, 0),
                "date_in_out": datetime(2026, 9, day, 15, 0),
                "state_edoc": state,
                "fiscal_line_ids": line_vals,
            }
        )

    def _declaration(self, **vals):
        self.env["l10n_br_sped.mixin"]._flush_registers("efd_pis_cofins")
        model = self.env["l10n_br_sped.efd_pis_cofins.0000"].with_company(self.matriz)
        values = model._map_from_odoo(self.matriz, None, None)
        values.update(
            {
                "company_id": self.matriz.id,
                "DT_INI": date(2026, 9, 1),
                "DT_FIN": date(2026, 9, 30),
            }
        )
        values.update(vals)
        declaration = model.create(values)
        declaration.button_populate_sped_from_odoo()
        return declaration

    def _registers(self, declaration, code):
        return self.env[f"l10n_br_sped.efd_pis_cofins.{code}"].search(
            [("declaration_id", "=", declaration.id)]
        )

    def _lines(self, text, code):
        return [line for line in text.splitlines() if line.startswith(f"|{code}|")]

    # ------------------------------------------------------------------
    # Leiaute 006 em vigor
    # ------------------------------------------------------------------

    def test_layout_without_block_p_and_0145(self):
        """NT 09/2024: o 0145 e o bloco P não existem a partir de 2025."""
        for code in ("0145", "p001", "p010", "p100", "p200"):
            self.assertNotIn(f"l10n_br_sped.efd_pis_cofins.{code}", self.env)

    def test_layout_d500_nfcom_key(self):
        """NT 09/2024: D500 ganha o campo 23 CHV_DOC_E (NFCom, modelo 62)."""
        spec = self.env["l10n_br_sped.efd_pis_cofins.6.d500"]
        names = [name for name, _f in spec._ordered_fields() if name.isupper()]
        self.assertEqual(len(names), 22)
        self.assertEqual(names[-1], "CHV_DOC_E")

    def test_layout_m210_from_2019(self):
        """Guia 1.35: o M210 em vigor desde 2019 tem 16 campos."""
        spec = self.env["l10n_br_sped.efd_pis_cofins.6.m210"]
        names = [name for name, _f in spec._ordered_fields() if name.isupper()]
        self.assertEqual(
            names[:6],
            [
                "COD_CONT",
                "VL_REC_BRT",
                "VL_BC_CONT",
                "VL_AJUS_ACRES_BC",
                "VL_AJUS_REDUC_BC",
                "VL_BC_CONT_AJUS",
            ],
        )
        self.assertEqual(len(names), 15)

    # ------------------------------------------------------------------
    # NT 11/2026
    # ------------------------------------------------------------------

    def test_nt_11_2026_new_models_use_paper_codes(self):
        """NFAg (75) e NFGas (76) entram como 29 e 28."""
        self.assertEqual(_cod_mod("75"), "29")
        self.assertEqual(_cod_mod("76"), "28")
        self.assertEqual(_cod_mod("55"), "55")

    def test_nt_11_2026_cbs_ibs_not_in_document_or_item_value(self):
        """CBS e IBS destacados não somam no VL_DOC nem no VL_ITEM."""
        cbs_group = self.env.ref("l10n_br_fiscal.tax_group_cbs")
        ibs_group = self.env.ref("l10n_br_fiscal.tax_group_ibs")
        # grupo fora do preço: o motor fiscal soma o tributo ao total
        (cbs_group | ibs_group).write({"tax_include": False})
        document = self._document(
            lines=[
                {
                    "cbs_tax_id": self.env.ref("l10n_br_fiscal.tax_cbs_0_9").id,
                    "cbs_base": 100.0,
                    "cbs_percent": 0.9,
                    "cbs_value": 0.9,
                    "ibs_tax_id": self.env.ref("l10n_br_fiscal.tax_ibs_0_1").id,
                    "ibs_base": 100.0,
                    "ibs_percent": 0.1,
                    "ibs_value": 0.1,
                    "amount_tax_not_included": 1.0,
                }
            ]
        )
        self.assertAlmostEqual(document.fiscal_amount_total, 101.0)
        declaration = self._declaration()
        c100 = self._registers(declaration, "c100")
        self.assertAlmostEqual(c100.VL_DOC, 100.0)
        self.assertAlmostEqual(self._registers(declaration, "c170").VL_ITEM, 100.0)
        text = declaration._generate_sped_text()
        self.assertIn("|100,00|", self._lines(text, "C100")[0])

    def test_nt_11_2026_included_taxes_are_not_subtracted(self):
        """Com o grupo "incluído no preço", o total já não tem CBS/IBS."""
        self.env.ref("l10n_br_fiscal.tax_group_cbs").write({"tax_include": True})
        self._document(
            lines=[
                {
                    "cbs_tax_id": self.env.ref("l10n_br_fiscal.tax_cbs_0_9").id,
                    "cbs_value": 0.9,
                }
            ]
        )
        declaration = self._declaration()
        self.assertAlmostEqual(self._registers(declaration, "c100").VL_DOC, 100.0)

    # ------------------------------------------------------------------
    # Estabelecimentos e documentos
    # ------------------------------------------------------------------

    def test_establishments_by_cnpj_root(self):
        """Uma escrituração por pessoa jurídica: 0140 e C010 por filial."""
        doc_matriz = self._document()
        doc_filial = self._document(company=self.filial)
        declaration = self._declaration()
        self.assertEqual(declaration.establishment_ids, self.matriz | self.filial)
        # UNID é o código da unidade e o NCM vai só com dígitos
        self.assertEqual(
            set(self._registers(declaration, "0190").mapped("UNID")),
            {self.product.uom_id.code[:6]},
        )
        self.assertEqual(
            set(self._registers(declaration, "0200").mapped("COD_NCM")), {"94033000"}
        )
        reg_0140 = self._registers(declaration, "0140")
        self.assertEqual(
            sorted(reg_0140.mapped("CNPJ")),
            sorted([self.matriz.vat, self.filial.vat]),
        )
        c010 = self._registers(declaration, "c010")
        self.assertEqual(len(c010), 2)
        for reg in c010:
            company = self.matriz if reg.CNPJ == self.matriz.vat else self.filial
            expected = doc_matriz if company == self.matriz else doc_filial
            self.assertEqual(reg.reg_C100_ids.mapped("res_id"), expected.ids)
        # a filial retirada da declaração some do arquivo
        declaration2 = self._declaration(establishment_ids=[(6, 0, self.matriz.ids)])
        self.assertEqual(len(self._registers(declaration2, "c010")), 1)

    def test_transfer_is_not_revenue(self):
        """Guia, C100: documento sem receita nem crédito não é escriturado."""
        self._document(lines=[{"cfop_id": self.cfop_transf.id}])
        declaration = self._declaration()
        self.assertFalse(self._registers(declaration, "c100"))
        self.assertFalse(self._registers(declaration, "c010"))

    def test_cancelled_document_without_children(self):
        """Guia, C100: cancelada leva só a chave do registro, sem C170."""
        self._document(state="cancelada")
        declaration = self._declaration()
        c100 = self._registers(declaration, "c100")
        self.assertEqual(c100.COD_SIT, "02")
        self.assertFalse(c100.reg_C170_ids)
        text = declaration._generate_sped_text()
        line = self._lines(text, "C100")[0].split("|")
        # VL_DOC (campo 12) vazio
        self.assertEqual(line[12], "")
        self.assertFalse(declaration.validate_sped_text(text))

    def test_document_date_in_local_time(self):
        """Nota das 22h de 30/09 em Brasília é de setembro (01h de 01/10 UTC)."""
        document = self._document()
        document.document_date = datetime(2026, 10, 1, 1, 0)
        document.date_in_out = datetime(2026, 10, 1, 1, 0)
        declaration = self._declaration()
        self.assertEqual(self._registers(declaration, "c100").DT_DOC, date(2026, 9, 30))

    # ------------------------------------------------------------------
    # Bloco M
    # ------------------------------------------------------------------

    def test_block_m_from_documents(self):
        """M210 fecha com os itens escriturados (Guia 1.35, M210 campos 03/04)."""
        self._document(lines=[{}, {}])
        self._document(
            lines=[
                {
                    "pis_cst_id": self.cst_pis_04.id,
                    "pis_base": 0.0,
                    "pis_percent": 0.0,
                    "pis_value": 0.0,
                    "cofins_cst_id": self.cst_cofins_04.id,
                    "cofins_base": 0.0,
                    "cofins_percent": 0.0,
                    "cofins_value": 0.0,
                }
            ]
        )
        # natureza da receita (tabela 4.3.10, monofásicos) pelo NCM
        self.env["l10n_br_fiscal.tax.pis.cofins"].search(
            [("sped_table", "=", "4.3.10")]
        ).unlink()
        nature = self.env["l10n_br_fiscal.tax.pis.cofins"].create(
            {
                "code": "999",
                "name": "Natureza fictícia",
                "sped_table": "4.3.10",
                "ncms": self.product.ncm_id.code,
            }
        )
        self.assertIn(self.product.ncm_id, nature.ncm_ids)
        declaration = self._declaration()
        m210 = self._registers(declaration, "m210")
        self.assertEqual(m210.COD_CONT, "01")
        self.assertAlmostEqual(m210.ALIQ_PIS, 1.65)
        self.assertAlmostEqual(m210.VL_BC_CONT, 200.0)
        self.assertAlmostEqual(m210.VL_CONT_APUR, 3.3)
        m200 = self._registers(declaration, "m200")
        self.assertAlmostEqual(m200.VL_TOT_CONT_NC_PER, 3.3)
        self.assertAlmostEqual(m200.VL_CONT_NC_REC, 3.3)
        m205 = self._registers(declaration, "m205")
        self.assertEqual((m205.NUM_CAMPO, m205.COD_REC), ("08", "691201"))
        m610 = self._registers(declaration, "m610")
        self.assertAlmostEqual(m610.VL_CONT_APUR, 15.2)
        # CST 04 (monofásico na revenda) vai para o M400/M800
        m400 = self._registers(declaration, "m400")
        self.assertEqual(m400.CST_PIS, "04")
        self.assertAlmostEqual(m400.VL_TOT_REC, 100.0)
        self.assertEqual(m400.reg_M410_ids.NAT_REC, "999")
        text = declaration._generate_sped_text()
        self.assertEqual(
            self._lines(text, "M210")[0],
            "|M210|01|200,00|200,00|0|0|200,00|1,65|||3,30|0|0|||3,30|",
        )
        self.assertEqual(declaration.validate_sped_text(text), [])

    def _assessment(self, tax, adjustment=None):
        fiscal_group = self.env.ref(f"l10n_br_fiscal.tax_group_{tax}")
        group = self.env["account.tax.group"].create(
            {
                "name": f"{tax.upper()} fictício",
                "company_id": self.matriz.id,
                "fiscal_tax_group_id": fiscal_group.id,
                "regime": "non_cumulative",
            }
        )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.matriz.id,
                "tax_group_id": group.id,
                "date_from": date(2026, 9, 1),
                "date_to": date(2026, 9, 30),
            }
        )
        if adjustment:
            self.env["l10n_br_tax.assessment.line"].create(
                dict(
                    adjustment,
                    assessment_id=assessment.id,
                    source="manual",
                )
            )
        assessment.state = "posted"
        return assessment

    def test_nt_12_2026_benefit_reduction_as_m220(self):
        """NT 12/2026: a redução da LC 224/2025 entra como acréscimo no M220."""
        self._document()
        self._assessment(
            "pis",
            {
                "kind": "debit",
                "tax_amount": 2.5,
                "description": "Redução de benefício - LC 224/2025",
            },
        )
        declaration = self._declaration()
        m210 = self._registers(declaration, "m210")
        self.assertEqual(m210.COD_CONT, "01")
        self.assertAlmostEqual(m210.VL_AJUS_ACRES, 2.5)
        self.assertAlmostEqual(m210.VL_CONT_PER, 1.65 + 2.5)
        m220 = m210.reg_M220_ids
        self.assertEqual((m220.IND_AJ, m220.COD_AJ), ("1", "03"))
        self.assertAlmostEqual(m220.VL_AJ, 2.5)
        self.assertAlmostEqual(
            self._registers(declaration, "m200").VL_TOT_CONT_NC_PER, 4.15
        )

    def test_nt_12_2026_creates_basic_rate_m210(self):
        """NT 12/2026: sem M210 01, ele é criado para receber o ajuste."""
        self._document(
            lines=[
                {
                    "pis_cst_id": self.cst_pis_04.id,
                    "pis_base": 0.0,
                    "pis_percent": 0.0,
                    "pis_value": 0.0,
                }
            ]
        )
        self._assessment(
            "pis",
            {
                "kind": "debit",
                "tax_amount": 1.0,
                "description": "Redução de benefício - LC 224/2025",
            },
        )
        declaration = self._declaration()
        m210 = self._registers(declaration, "m210")
        self.assertEqual((m210.COD_CONT, m210.ALIQ_PIS), ("01", 1.65))
        self.assertAlmostEqual(m210.VL_BC_CONT, 0.0)
        self.assertAlmostEqual(m210.VL_CONT_PER, 1.0)

    def test_divergence_with_assessment_is_logged(self):
        """Débito da apuração diferente do dos documentos vai para o chatter."""
        self._document()
        self._assessment("pis")
        declaration = self._declaration()
        messages = declaration.message_ids.mapped("body")
        self.assertTrue(
            any("débito de 0.00" in body and "1.65" in body for body in messages)
        )

    # ------------------------------------------------------------------
    # Arquivo
    # ------------------------------------------------------------------

    def test_regime_from_profit_calculation(self):
        self._document()
        declaration = self._declaration()
        self.assertEqual(declaration.cod_inc_trib, "1")
        reg_0110 = self._registers(declaration, "0110")
        self.assertEqual(
            (reg_0110.COD_INC_TRIB, reg_0110.IND_APRO_CRED, reg_0110.COD_TIPO_CONT),
            ("1", "1", "1"),
        )

    def test_number_format(self):
        """Monetário com 2 casas e vírgula; zero só onde o leiaute exige."""
        c100 = self.env["l10n_br_sped.efd_pis_cofins.c100"]
        vl_doc = c100._fields["VL_DOC"]
        vl_desc = c100._fields["VL_DESC"]
        self.assertEqual(c100._format_field_value(vl_doc, 10.5), "10,50")
        self.assertEqual(c100._format_field_value(vl_doc, 0.0), "0")
        self.assertEqual(c100._format_field_value(vl_desc, 0.0), "")
        # alfanumérico sem caractere não imprimível nem pipe (Seção 3, a)
        descr = self.env["l10n_br_sped.efd_pis_cofins.c170"]._fields["DESCR_COMPL"]
        self.assertEqual(
            c100._format_field_value(descr, "FILTRO\tDE|OLEO"), "FILTRO DE OLEO"
        )

    def test_generated_file_passes_structural_validator(self):
        self._document()
        self._document(company=self.filial, state="cancelada")
        declaration = self._declaration()
        text = declaration._generate_sped_text()
        self.assertEqual(declaration.validate_sped_text(text), [])
        self.assertTrue(text.startswith("|0000|006|0|"))
        for block in ("A", "C", "D", "F", "I", "M", "1"):
            self.assertIn(f"|{block}001|", text)
        self.assertNotIn("|P001|", text)

    def test_c170_zero_values_written_when_cst_requires(self):
        """CST 01 com valor zero: base, alíquota e valor vão como 0, não vazios."""
        self._document(
            lines=[
                {
                    "pis_base": 0.0,
                    "pis_percent": 0.0,
                    "pis_value": 0.0,
                    "cofins_base": 0.0,
                    "cofins_percent": 0.0,
                    "cofins_value": 0.0,
                }
            ]
        )
        declaration = self._declaration()
        fields = self._lines(declaration._generate_sped_text(), "C170")[0].split("|")
        # CST_PIS (25), VL_BC_PIS (26), ALIQ_PIS (27), VL_PIS (30)
        self.assertEqual(
            (fields[25], fields[26], fields[27], fields[30]), ("01", "0", "0", "0")
        )

    # ------------------------------------------------------------------
    # Regime cumulativo (Lucro Presumido)
    # ------------------------------------------------------------------

    def _cumulative_lines(self, **extra):
        vals = {
            "pis_base": 100.0,
            "pis_percent": 0.65,
            "pis_value": 0.65,
            "cofins_base": 100.0,
            "cofins_percent": 3.0,
            "cofins_value": 3.0,
        }
        vals.update(extra)
        return [vals]

    def test_cumulative_regime_from_profit_calculation(self):
        """Lucro Presumido: 0110 = 2, M210 51 e DARF do cumulativo."""
        self.matriz.profit_calculation = "presumed"
        self._document(lines=self._cumulative_lines())
        declaration = self._declaration()
        self.assertEqual(declaration.cod_inc_trib, "2")
        reg_0110 = self._registers(declaration, "0110")
        self.assertEqual(
            (reg_0110.COD_INC_TRIB, reg_0110.IND_APRO_CRED, reg_0110.IND_REG_CUM),
            ("2", False, "9"),
        )
        m210 = self._registers(declaration, "m210")
        self.assertEqual((m210.COD_CONT, m210.ALIQ_PIS), ("51", 0.65))
        m200 = self._registers(declaration, "m200")
        self.assertAlmostEqual(m200.VL_TOT_CONT_CUM_PER, 0.65)
        self.assertAlmostEqual(m200.VL_CONT_CUM_REC, 0.65)
        self.assertAlmostEqual(m200.VL_TOT_CONT_NC_PER, 0.0)
        m205 = self._registers(declaration, "m205")
        self.assertEqual((m205.NUM_CAMPO, m205.COD_REC), ("12", "810902"))
        self.assertEqual(self._registers(declaration, "m605").COD_REC, "217201")
        text = declaration._generate_sped_text()
        self.assertEqual(declaration.validate_sped_text(text), [])

    def test_cumulative_regime_skips_purchases(self):
        """Guia 1.35, Seção 4: entrada sem crédito não precisa ser informada."""
        self.matriz.profit_calculation = "presumed"
        self._document(lines=self._cumulative_lines())
        self._document(
            operation=self.env.ref("l10n_br_fiscal.fo_compras"),
            issuer="partner",
            lines=[{"cfop_id": self.env.ref("l10n_br_fiscal.cfop_1102").id}],
        )
        declaration = self._declaration()
        self.assertEqual(self._registers(declaration, "c100").mapped("IND_OPER"), ["1"])
        # no não cumulativo a mesma entrada é escriturada
        self.matriz.profit_calculation = "real"
        declaration = self._declaration()
        self.assertEqual(
            sorted(self._registers(declaration, "c100").mapped("IND_OPER")),
            ["0", "1"],
        )

    def test_nat_rec_rule_for_legal_framework(self):
        """CST 08: a natureza (tabela 4.3.15) vem da regra do contador."""
        Rule = self.env["l10n_br_sped_efd_pis_cofins.nat_rec.rule"]
        Rule.create({"cst": "08", "nat_rec": "999", "note": "geral"})
        Rule.create(
            {
                "cst": "08",
                "ncm_prefix": "9403",
                "nat_rec": "401",
                "company_id": self.matriz.id,
            }
        )
        cst_08 = {
            "pis_cst_id": self.env.ref("l10n_br_fiscal.cst_pis_08").id,
            "pis_base": 0.0,
            "pis_percent": 0.0,
            "pis_value": 0.0,
            "cofins_cst_id": self.env.ref("l10n_br_fiscal.cst_cofins_08").id,
            "cofins_base": 0.0,
            "cofins_percent": 0.0,
            "cofins_value": 0.0,
        }
        self._document(lines=[cst_08])
        declaration = self._declaration()
        m400 = self._registers(declaration, "m400")
        self.assertEqual(m400.CST_PIS, "08")
        # o prefixo de NCM mais longo, da empresa, vence a regra geral
        self.assertEqual(m400.reg_M410_ids.NAT_REC, "401")
        self.assertEqual(
            self._registers(declaration, "m800").reg_M810_ids.NAT_REC, "401"
        )
        self.assertEqual(Rule._find(self.matriz, "08", "84212300"), "999")
        self.assertEqual(Rule._find(self.matriz, "07", "84212300"), "")

    def test_c120_from_import_declaration(self):
        """NF-e de importação: C120 por DI/DUIMP, sem repetir o número."""
        if "nfe.40.di" not in self.env:
            self.skipTest("l10n_br_nfe não instalado: sem o grupo DI da NF-e")
        document = self._document(
            operation=self.env.ref("l10n_br_fiscal.fo_compras"),
            lines=[
                {"cfop_id": self.env.ref("l10n_br_fiscal.cfop_3102").id},
                {"cfop_id": self.env.ref("l10n_br_fiscal.cfop_3102").id},
            ],
        )
        for line in document.fiscal_line_ids:
            self.env["nfe.40.di"].create(
                {
                    "nfe40_nDI": "26BR00000000001",
                    "nfe40_dDI": date(2026, 9, 1),
                    "nfe40_DI_prod_id": line.id,
                }
            )
        declaration = self._declaration()
        c120 = self._registers(declaration, "c120")
        self.assertEqual(len(c120), 1)
        self.assertEqual((c120.COD_DOC_IMP, c120.NUM_DOC_IMP), ("2", "26BR00000000001"))
        self.assertAlmostEqual(c120.VL_PIS_IMP, 3.3)
        self.assertAlmostEqual(c120.VL_COFINS_IMP, 15.2)


@tagged("post_install", "-at_install")
class TestDeclarationCompanies(TransactionCase):
    """A declaração lê os documentos das empresas dela, não do seletor."""

    def test_switcher_does_not_limit_the_establishments(self):
        Company = self.env["res.company"]
        main = self.env.company
        branch = Company.create({"name": "Filial ficticia SPED", "parent_id": main.id})
        user = self.env["res.users"].create(
            {
                "name": "Fiscal ficticio",
                "login": "fiscal.ficticio.sped",
                "company_id": main.id,
                "company_ids": [(6, 0, (main | branch).ids)],
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("l10n_br_fiscal.group_manager").id),
                ],
            }
        )
        declaration = (
            self.env["l10n_br_sped.efd_pis_cofins.0000"]
            .with_user(user)
            .with_context(allowed_company_ids=[main.id])
            .create(
                {"company_id": main.id, "DT_INI": "2026-09-01", "DT_FIN": "2026-09-30"}
            )
        )
        self.assertIn(branch, declaration.establishment_ids)
        scoped = declaration._with_sped_companies()
        self.assertEqual(set(scoped.env.companies.ids), {main.id, branch.id})
        # sem acesso a uma filial, erro claro em vez de arquivo parcial
        user.company_ids = [(6, 0, main.ids)]
        with self.assertRaises(UserError):
            declaration.with_user(user)._with_sped_companies()
