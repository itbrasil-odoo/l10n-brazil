# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from io import StringIO
from unittest.mock import patch

from odoo.tests import common, tagged

DOCUMENTS = (
    "odoo.addons.l10n_br_sped_efd_icms_ipi.models.sped_efd_icms_ipi"
    ".icms_document_totals"
)


@tagged("post_install", "-at_install")
class TestBlocoE(common.TransactionCase):
    """O E110 soma os documentos (campos 02 e 06) e a apuração (o resto).

    Débitos e créditos vêm do C190, como o Guia define e o PVA confere; os
    ajustes manuais, o saldo anterior e as deduções vêm da apuração. Os
    totais dos documentos são simulados aqui (1000 de débito, 400 de
    crédito); a soma real está coberta em test_rules_2026. Estes testes
    conferem valor, não presença: um E110 gerado com zeros passaria num teste
    de presença e reprovaria no PVA.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group = cls.env["account.tax.group"].create(
            {
                "name": "ICMS (bloco E)",
                "fiscal_tax_group_id": cls.env.ref("l10n_br_fiscal.tax_group_icms").id,
            }
        )
        cls.assessment = cls.env["l10n_br_tax.assessment"].create(
            {
                "company_id": cls.company.id,
                "tax_group_id": cls.group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        Line = cls.env["l10n_br_tax.assessment.line"]
        # apurado das move lines: campos 02 e 06 do E110
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "debit",
                "tax_amount": 1000.0,
                "source": "computed",
            }
        )
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "credit",
                "tax_amount": 400.0,
                "source": "computed",
            }
        )
        # ajustes manuais: viram E111 e alimentam os campos 04, 05 e 12
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "debit",
                "tax_amount": 50.0,
                "source": "manual",
                "adjustment_code": "SP000001",
                "description": "outros débitos",
            }
        )
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "credit_reversal",
                "tax_amount": 20.0,
                "source": "manual",
                "adjustment_code": "SP010001",
                "description": "estorno de crédito",
            }
        )
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "deduction",
                "tax_amount": 70.0,
                "source": "manual",
                "adjustment_code": "SP040001",
                "description": "dedução",
            }
        )
        cls.assessment.state = "posted"

        cls.declaration = cls.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": cls.company.id,
                "DT_INI": "2026-07-01",
                "DT_FIN": "2026-07-31",
            }
        )

    def _pull_bloco_e(self, documents=None):
        # mesmo contexto que `button_populate_sped_from_odoo` monta: o
        # `default_declaration_id` e quem amarra cada registro criado a
        # declaracao, e sem ele o create esbarra no not-null.
        model = self.env["l10n_br_sped.efd_icms_ipi.e100"].with_context(
            company_id=self.company.id,
            declaration=self.declaration,
            default_declaration_id=self.declaration.id,
        )
        documents = documents or {
            "debit": 1000.0,
            "credit": 400.0,
            "extemporaneous": 0.0,
        }
        with patch(DOCUMENTS, return_value=documents):
            model._pull_records_from_odoo("efd_icms_ipi", 2, log_msg=StringIO())
        return self.env["l10n_br_sped.efd_icms_ipi.e100"].search(
            [("declaration_id", "=", self.declaration.id)]
        )

    def test_e110_serializes_the_assessment(self):
        e100 = self._pull_bloco_e()
        self.assertEqual(len(e100), 1)
        e110 = e100.reg_E110_ids
        self.assertEqual(len(e110), 1, "E110 é 1:1 dentro do E100")

        self.assertAlmostEqual(e110.VL_TOT_DEBITOS, 1000.0, places=2)
        self.assertAlmostEqual(e110.VL_TOT_CREDITOS, 400.0, places=2)
        self.assertAlmostEqual(e110.VL_TOT_AJ_DEBITOS, 50.0, places=2)
        self.assertAlmostEqual(e110.VL_ESTORNOS_CRED, 20.0, places=2)
        self.assertAlmostEqual(e110.VL_TOT_DED, 70.0, places=2)
        # 1000 + 50 + 20 - 400 = 670 de saldo devedor apurado
        self.assertAlmostEqual(e110.VL_SLD_APURADO, 670.0, places=2)
        # 670 - 70 de deducao
        self.assertAlmostEqual(e110.VL_ICMS_RECOLHER, 600.0, places=2)
        self.assertAlmostEqual(e110.VL_SLD_CREDOR_TRANSPORTAR, 0.0, places=2)

    def test_e110_matches_the_assessment_when_books_agree(self):
        """Contabilidade igual aos documentos: E110 igual à apuração."""
        e110 = self._pull_bloco_e().reg_E110_ids
        self.assertAlmostEqual(
            e110.VL_ICMS_RECOLHER, self.assessment.amount_payable, places=2
        )
        self.assertAlmostEqual(
            e110.VL_SLD_APURADO, self.assessment.assessed_balance, places=2
        )

    def test_e110_follows_the_documents_when_books_disagree(self):
        """Crédito que a contabilidade jogou no custo ainda entra no E110.

        A compra com crédito de 300 de ICMS sem linha a recuperar: a apuração
        (contabilidade) não vê o crédito, o C190 vê. O PVA confere o E110
        contra o C190, então o arquivo segue os documentos, e a divergência
        fica registrada na declaração para alguém corrigir a contabilidade.
        """
        e110 = self._pull_bloco_e(
            {"debit": 1000.0, "credit": 700.0, "extemporaneous": 0.0}
        ).reg_E110_ids
        self.assertAlmostEqual(e110.VL_TOT_CREDITOS, 700.0, places=2)
        # 1000 + 50 + 20 - 700 = 370; menos 70 de dedução
        self.assertAlmostEqual(e110.VL_SLD_APURADO, 370.0, places=2)
        self.assertAlmostEqual(e110.VL_ICMS_RECOLHER, 300.0, places=2)
        self.assertAlmostEqual(e110.reg_E116_ids.VL_OR, 300.0, places=2)
        message = self.declaration.message_ids[:1]
        self.assertIn("700.00", message.body)
        self.assertIn("400.00", message.body)

    def test_credit_balance_has_no_obligation(self):
        """Saldo credor: E110 transporta o crédito e não há E116.

        Guia Prático 3.2.4, E110 campos 11 e 12: a dedução é informada
        inteira mesmo com saldo apurado zero, e o valor absoluto da expressão
        vai para o saldo credor a transportar "adicionado ao valor total das
        deduções".
        """
        e110 = self._pull_bloco_e(
            {"debit": 100.0, "credit": 900.0, "extemporaneous": 0.0}
        ).reg_E110_ids
        self.assertAlmostEqual(e110.VL_SLD_APURADO, 0.0, places=2)
        self.assertAlmostEqual(e110.VL_ICMS_RECOLHER, 0.0, places=2)
        self.assertAlmostEqual(e110.VL_TOT_DED, 70.0, places=2)
        # |100 + 50 + 20 - 900| = 730, mais 70 de dedução
        self.assertAlmostEqual(e110.VL_SLD_CREDOR_TRANSPORTAR, 800.0, places=2)
        self.assertFalse(e110.reg_E116_ids)

    def test_deduction_above_the_balance_is_carried(self):
        """Campo 13: dedução maior que o saldo devedor vira saldo credor."""
        e110 = self._pull_bloco_e(
            {"debit": 400.0, "credit": 400.0, "extemporaneous": 0.0}
        ).reg_E110_ids
        # 400 + 50 + 20 - 400 = 70 apurado; 70 - 70 de dedução = 0
        self.assertAlmostEqual(e110.VL_SLD_APURADO, 70.0, places=2)
        self.assertAlmostEqual(e110.VL_ICMS_RECOLHER, 0.0, places=2)
        self.assertAlmostEqual(e110.VL_SLD_CREDOR_TRANSPORTAR, 0.0, places=2)

    def test_extemporaneous_documents_go_to_deb_esp(self):
        """Campo 03/15: documento extemporâneo sai do débito e vai ao DEB_ESP."""
        e110 = self._pull_bloco_e(
            {"debit": 1000.0, "credit": 400.0, "extemporaneous": 25.0}
        ).reg_E110_ids
        self.assertAlmostEqual(e110.VL_TOT_DEBITOS, 1000.0, places=2)
        self.assertAlmostEqual(e110.DEB_ESP, 25.0, places=2)
        # E116: VL_OR = ICMS a recolher + DEB_ESP
        self.assertAlmostEqual(e110.reg_E116_ids.VL_OR, 625.0, places=2)

    def test_e111_only_carries_manual_adjustments(self):
        """Linha apurada não vira E111: já está somada no campo 02 do E110."""
        e111 = self._pull_bloco_e().reg_E110_ids.reg_E111_ids
        self.assertEqual(len(e111), 3)
        self.assertEqual(
            sorted(e111.mapped("COD_AJ_APUR")),
            ["SP000001", "SP010001", "SP040001"],
        )
        estorno = e111.filtered(lambda r: r.COD_AJ_APUR == "SP010001")
        self.assertAlmostEqual(estorno.VL_AJ_APUR, 20.0, places=2)
        self.assertEqual(estorno.DESCR_COMPL_AJ, "estorno de crédito")

    def test_only_a_posted_assessment_is_serialized(self):
        """Rascunho e apuração não encerrada ficam fora do arquivo entregue."""
        for state in ("draft", "computed"):
            self.assessment.state = state
            self.assertFalse(
                self._pull_bloco_e().reg_E110_ids,
                f"apuração {state} não pode entrar no arquivo",
            )
            self.env["l10n_br_sped.efd_icms_ipi.e100"].search(
                [("declaration_id", "=", self.declaration.id)]
            ).unlink()


@tagged("post_install", "-at_install")
class TestBlocoE5(common.TransactionCase):
    """O bloco E5xx (IPI) serializa a apuração de IPI, como o E110 faz no ICMS.

    Sem apuração de IPI encerrada, a árvore E500 inteira fica fora do
    arquivo: é o layout de um contribuinte que não é do IPI.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group = cls.env["account.tax.group"].create(
            {
                "name": "IPI (bloco E5)",
                "fiscal_tax_group_id": cls.env.ref("l10n_br_fiscal.tax_group_ipi").id,
            }
        )
        cls.assessment = cls.env["l10n_br_tax.assessment"].create(
            {
                "company_id": cls.company.id,
                "tax_group_id": cls.group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        Line = cls.env["l10n_br_tax.assessment.line"]
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "debit",
                "tax_amount": 500.0,
                "source": "computed",
            }
        )
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "credit",
                "tax_amount": 200.0,
                "source": "computed",
            }
        )
        # ajuste manual a débito: vira E530 e entra no campo 05 do E520
        Line.create(
            {
                "assessment_id": cls.assessment.id,
                "kind": "debit",
                "tax_amount": 30.0,
                "source": "manual",
                "adjustment_code": "199",
                "description": "outros débitos de IPI",
            }
        )
        cls.assessment.state = "posted"

        # o bloco E5 (IPI) só existe para contribuinte do IPI (IND_ATIV 0)
        cls.declaration = cls.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": cls.company.id,
                "DT_INI": "2026-07-01",
                "DT_FIN": "2026-07-31",
                "IND_ATIV": "0",
            }
        )

    def _pull_bloco_e5(self):
        model = self.env["l10n_br_sped.efd_icms_ipi.e500"].with_context(
            company_id=self.company.id,
            declaration=self.declaration,
            default_declaration_id=self.declaration.id,
        )
        model._pull_records_from_odoo("efd_icms_ipi", 2, log_msg=StringIO())
        return self.env["l10n_br_sped.efd_icms_ipi.e500"].search(
            [("declaration_id", "=", self.declaration.id)]
        )

    def test_e520_serializes_the_ipi_assessment(self):
        e500 = self._pull_bloco_e5()
        self.assertEqual(len(e500), 1)
        self.assertEqual(e500.IND_APUR, "0")
        e520 = e500.reg_E520_ids
        self.assertEqual(len(e520), 1, "E520 é 1:1 dentro do E500")

        self.assertAlmostEqual(e520.VL_DEB_IPI, 500.0, places=2)
        self.assertAlmostEqual(e520.VL_CRED_IPI, 200.0, places=2)
        # o leiaute dobra estornos dentro de "outros débitos/créditos"
        self.assertAlmostEqual(e520.VL_OD_IPI, 30.0, places=2)
        self.assertAlmostEqual(e520.VL_OC_IPI, 0.0, places=2)
        # 500 + 30 - 200 = 330 a recolher
        self.assertAlmostEqual(e520.VL_SD_IPI, 330.0, places=2)
        self.assertAlmostEqual(e520.VL_SC_IPI, 0.0, places=2)
        self.assertAlmostEqual(e520.VL_SD_IPI, self.assessment.amount_payable, places=2)

    def test_e530_only_carries_manual_adjustments(self):
        e530 = self._pull_bloco_e5().reg_E520_ids.reg_E530_ids
        self.assertEqual(len(e530), 1, "linha apurada não vira E530")
        self.assertEqual(e530.IND_AJ, "0")
        self.assertEqual(e530.COD_AJ, "199")
        self.assertAlmostEqual(e530.VL_AJ, 30.0, places=2)
        self.assertEqual(e530.DESCR_AJ, "outros débitos de IPI")

    def test_no_ipi_assessment_no_e500(self):
        """Quem não é contribuinte do IPI não tem árvore E500 no arquivo."""
        self.assessment.state = "draft"
        self.assertFalse(self._pull_bloco_e5())
