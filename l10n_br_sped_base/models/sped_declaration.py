# Copyright 2023 - TODAY, Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

import base64
import logging
from collections import defaultdict
from io import StringIO

from lxml.builder import E

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .sped_mixin import LAYOUT_VERSIONS, SPED_ENCODING

_logger = logging.getLogger(__name__)


class SpedDeclaration(models.AbstractModel):
    _name = "l10n_br_sped.declaration"
    _description = "Sped Declaration"
    _inherit = ["l10n_br_sped.mixin", "mail.thread", "mail.activity.mixin"]

    @api.model
    def _get_default_dt_ini(self):
        dt = fields.Date.context_today(self)
        return dt.replace(year=dt.year - 1)

    @api.model
    def _get_default_dt_fin(self):
        dt = fields.Date.context_today(self)
        return dt.replace(year=dt.year + 1)

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=[("draft", "Draft"), ("done", "Done")],
        readonly=True,
        tracking=True,
        copy=False,
        default="draft",
        help="State of the declaration. When the state is set to 'Done', "
        "the parameters become read-only.",
    )
    # filter = fields.Char()

    DT_INI = fields.Date(
        string="Start Date",
        default=_get_default_dt_ini,
    )

    DT_FIN = fields.Date(
        string="End Date",
        default=_get_default_dt_fin,
    )

    split_sped_by_bloco = fields.Boolean()

    pull_error = fields.Text(
        string="Pull errors",
        readonly=True,
        copy=False,
        help="Registers whose pull from Odoo failed in the last 'Pull Registers "
        "from Odoo'. While there is any, the SPED file is not generated: the "
        "register would simply be missing from a file that still looks valid.",
    )

    debug = fields.Boolean(
        help=(
            "If True, will pull draft account moves and "
            "draft fiscal documents from a larger date period "
            "to help developpers develop and debug the mappings"
        )
    )

    fiscal_document_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.document",
        compute="_compute_fiscal_documents",
    )

    fiscal_document_partner_ids = fields.One2many(
        comodel_name="res.partner", compute="_compute_fiscal_documents"
    )

    fiscal_document_line_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.document.line", compute="_compute_fiscal_documents"
    )

    fiscal_product_ids = fields.One2many(
        comodel_name="product.product", compute="_compute_fiscal_documents"
    )

    fiscal_operation_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.operation", compute="_compute_fiscal_documents"
    )

    fiscal_comment_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.comment", compute="_compute_fiscal_documents"
    )

    fiscal_uom_ids = fields.One2many(
        comodel_name="uom.uom", compute="_compute_fiscal_documents"
    )

    @api.model
    def default_get(self, fields_list):
        """Nasce com o registro 0000 preenchido a partir da empresa.

        Os campos do 0000 — CNPJ, nome empresarial, UF, inscrições e os
        indicadores — são obrigatórios no banco. Sem isto não se cria uma
        declaração pela tela sem digitar um a um o que o sistema já tem no
        cadastro da empresa, e a ECD exige quatorze deles. O mapeamento usado é
        o mesmo do "Pull Registers from Odoo", então a tela e o botão não podem
        divergir.
        """
        vals = super().default_get(fields_list)
        if not self._odoo_model or not hasattr(self, "_odoo_domain"):
            return vals
        esboco = self.new({"company_id": vals.get("company_id") or self.env.company.id})
        origem = self.env[self._odoo_model].search(
            self._odoo_domain(None, esboco), limit=1
        )
        if not origem:
            return vals
        for campo, valor in self._map_from_odoo(origem, None, esboco).items():
            if (
                campo in fields_list
                and campo not in vals
                and valor is not None
                and valor is not False
            ):
                vals[campo] = valor
        return vals

    @api.model
    def _get_kind(self) -> str:
        return self._name.replace(".0000", "").split(".")[-1]

    @api.depends("DT_FIN", "company_id.name")
    def _compute_display_name(self):
        for declaration in self:
            declaration.display_name = (
                f"{declaration.DT_FIN:%m-%Y}-"
                f"{declaration.company_id.name.replace(' ', '_')}"
            )

    @api.depends("company_id", "DT_INI", "DT_FIN")
    def _compute_fiscal_documents(self):
        for record in self:
            if record.debug:
                fiscal_document_ids = self.env["l10n_br_fiscal.document"].search(
                    [], order="id DESC", limit=100
                )
            else:
                fiscal_document_ids = self.env["l10n_br_fiscal.document"].search(
                    [
                        ("company_id", "=", record.company_id.id),
                        (
                            "state_edoc",
                            "in",
                            ("autorizada", "cancelada", "denegada", "inutilizada"),
                        ),
                        ("document_date", ">=", record.DT_INI),
                        ("document_date", "<=", record.DT_FIN),
                    ]
                )

            record.fiscal_document_partner_ids = fiscal_document_ids.mapped(
                "partner_id"
            )
            record.fiscal_document_line_ids = fiscal_document_ids.mapped(
                "fiscal_line_ids"
            )
            # TODO: Complementar com produtos dos outros blocos!!!!
            record.fiscal_product_ids = record.fiscal_document_line_ids.mapped(
                "product_id"
            )

            record.fiscal_document_ids = fiscal_document_ids
            record.fiscal_operation_ids = record.fiscal_document_ids.mapped(
                "fiscal_operation_id"
            )
            record.fiscal_comment_ids = record.fiscal_document_ids.mapped(
                "comment_ids"
            ) | record.fiscal_document_line_ids.mapped("comment_ids")

            # TODO: Complementar com unidades de medidas de outros blocos!!!
            record.fiscal_uom_ids = record.fiscal_document_line_ids.mapped("uom_id")

    def button_populate_sped_from_odoo(self):
        """Populate SPED registers from Odoo."""
        # TODO add cron pulling from Odoo for open declarations
        self.ensure_one()
        log_msg = StringIO()
        log_msg.write(f"<h3>{_('Pulled from Odoo')}</h3>")
        kind = self._get_kind()
        mixin_env = self.env["l10n_br_sped.mixin"].with_context(
            company_id=self.company_id.id,
            declaration=self,
            default_declaration_id=self.id,
        )
        top_registers = mixin_env._get_top_registers(kind)

        # O registro 0000 é a PRÓPRIA declaração, e `_pull_records_from_odoo`
        # só desce para os registros filhos. Sem mapear a declaração aqui, o
        # cabeçalho do arquivo sai com nome, CNPJ, IE e município em branco —
        # e o PVA recusa o arquivo logo na primeira linha.
        if self._odoo_model and hasattr(self, "_odoo_domain"):
            origem = self.env[self._odoo_model].search(
                self._odoo_domain(None, self), limit=1
            )
            if origem:
                vals = self._map_from_odoo(origem, None, self)
                self.write(
                    {k: v for k, v in vals.items() if v is not None and v is not False}
                )
                log_msg.write(
                    f"<p>0000: {self._odoo_model} → {origem.display_name}</p>"
                )

        errors = []
        for register_model in top_registers:  # Iterate over models, not instances
            try:
                with self.env.cr.savepoint():
                    register_model._pull_records_from_odoo(
                        kind, level=2, log_msg=log_msg
                    )
            except Exception as e:
                _logger.error(
                    f"Error pulling records for {register_model._name}: {e}",
                    exc_info=True,
                )
                log_msg.write(
                    "<p style='color:red;'>Error "
                    f"processing {register_model._name}: {e}</p>"
                )
                errors.append(f"{register_model._name}: {e}")
        # A register whose pull failed is simply ABSENT from the file, and the
        # structural validator cannot tell an absent register from one that
        # has no data (a lost 0140 still makes a well-formed file). So the
        # failure is kept on the declaration and blocks the file generation.
        self.pull_error = "\n".join(errors) or False
        self.message_post(body=log_msg.getvalue())

    def button_flush_registers(self):
        self.ensure_one()
        self.env["l10n_br_sped.mixin"]._flush_registers(self._get_kind(), self.id)
        self.message_post(
            body=f"<h3>{_('Flushed all Registers from Declaration!')}</h3>"
        )

    def button_done(self):
        self.state = "done"

    def button_draft(self):
        self.state = "draft"

    def button_create_sped_files(self):
        """Generate and attach the SPED file."""
        self.ensure_one()
        if self.pull_error:
            raise UserError(
                _(
                    "The last pull from Odoo failed for these registers, which "
                    "would be missing from the file. Fix the cause and pull "
                    "again before generating the SPED file:\n%s"
                )
                % self.pull_error
            )
        sped_txt = self._generate_sped_text()

        if self.split_sped_by_bloco:
            attachment_vals = self._split_sped_text_by_bloco(sped_txt)
        else:
            attachment_vals = [self._create_sped_attachment(sped_txt)]
        self.env["ir.attachment"].create(attachment_vals)

    def _split_sped_text_by_bloco(self, sped_txt):
        blocos = defaultdict(list)
        current_bloco = None
        for line in sped_txt.splitlines():
            # Uma linha de registro é "|REG|...". Qualquer outra coisa é
            # ignorada: linhas de resumo dos blocos 0 e 9, e fragmentos
            # deixados por um campo cujo valor continha quebra de linha. Isso
            # também garante que o split nunca estoure em linha corrompida.
            if not line.startswith("|") or len(line) < 2 or line[1] in "09":
                continue
            current_bloco = line[1]
            if current_bloco:
                blocos[current_bloco].append(line)

        attachments_vals = []
        for bloco, lines in blocos.items():
            if len(lines) < 3:  # empty bloco
                continue
            bloco_txt = "\n".join(lines)
            attachments_vals.append(self._create_sped_attachment(bloco_txt, bloco))

        return attachments_vals

    def _create_sped_attachment(self, text, bloco=None):
        kind = self._get_kind()
        if bloco:
            file_name = f"{kind.upper()}-bloco_{bloco}-{self.display_name}.txt"
        else:
            file_name = f"{kind.upper()}-{self.display_name}.txt"

        return {
            "name": file_name,
            "res_model": self._name,
            "res_id": self.id,
            # SPED files are ISO-8859-1, not the utf-8 of the default
            # encode(); errors="replace" keeps a character outside Latin-1
            # pasted in some journal item label from aborting the whole
            # file generation
            "datas": base64.b64encode(text.encode(SPED_ENCODING, errors="replace")),
            "mimetype": "application/txt",
            "type": "binary",
        }

    @api.onchange("company_id")
    def onchange_company_id(self):
        if not self.company_id:
            return
        res = self._map_from_odoo(
            self.company_id,
            None,
            None,
        )
        for k, v in res.items():
            setattr(self, k, v)

    @api.model
    def _append_view_header(self, form):
        """Append custom buttons to the form view header.

        The button labels go through `_()` because this view is built in code,
        not loaded from XML: there is no `ir.ui.view` record for a `.po` to
        reference, so a translation file can never reach them. Wrapped here,
        they resolve per request against the module's own catalogue.
        """
        header = E.header()
        header.append(
            E.button(
                name="button_populate_sped_from_odoo",
                type="object",
                invisible="state != 'draft'",
                string=_("Pull Registers from Odoo"),
                #            class="oe_highlight",
                groups="l10n_br_fiscal.group_manager",
            )
        )
        header.append(
            E.button(
                name="button_flush_registers",
                type="object",
                invisible="state != 'draft'",
                string=_("Flush Registers"),
                #            class="oe_highlight",
                groups="l10n_br_fiscal.group_manager",
            )
        )
        header.append(
            E.button(
                name="button_done",
                type="object",
                invisible="state != 'draft'",
                string=_("Set to Done"),
                #            class="oe_highlight",
                groups="l10n_br_fiscal.group_manager",
            )
        )
        header.append(
            E.button(
                name="button_draft",
                type="object",
                invisible="state != 'done'",
                string=_("Reset to Draft"),
                #            class="oe_highlight",
                groups="l10n_br_fiscal.group_manager",
            )
        )
        header.append(
            E.button(
                name="button_create_sped_files",
                type="object",
                invisible="state != 'done'",
                string=_("Generate SPED File"),
                #            class="oe_highlight",
                groups="l10n_br_fiscal.group_manager",
            )
        )

        header.append(E.field(name="state", widget="statusbar"))
        form.append(header)

    @api.model
    def _append_view_footer(self, form):
        """Append the chatter to the form view footer.

        Version 18 replaced the `<div class="oe_chatter">` block with a single
        `<chatter/>` tag. The old markup does not fail: the fields inside it are
        rendered as ordinary widgets, so the activity list shows up as a bare
        table under the sheet and the followers, which were only a `name` on the
        div, do not show up at all.
        """
        form.append(E.chatter())

    @api.model
    def _append_top_view_elements(self, group, inline=False):
        """Append top-level elements to the form view."""
        group.append(E.field(name="company_id"))
        group.append(E.field(name="split_sped_by_bloco"))
        group.append(E.field(name="debug"))
        group.append(E.separator(colspan="4"))

    def _skip_empty_blocks(self):
        """O bloco sem nenhum registro entra no arquivo, ou e omitido?

        A ECD escritura o bloco vazio com o indicador "1" (bloco sem dados);
        a ECF nao aceita: o PVA recusa o arquivo com "Organizacao hierarquica
        dos blocos/registros do arquivo esta fora dos padroes estabelecidos"
        e aponta como esperado o primeiro registro do proximo bloco com dados.
        Cada escrituracao responde por si.
        """
        return False

    def _generate_sped_text(self, version=None):
        """Generate SPED text from Odoo declaration records."""
        self.ensure_one()
        kind = self._get_kind()
        if version is None:
            version = LAYOUT_VERSIONS[kind]
        top_register_classes = self._get_top_registers(kind)
        sped = StringIO()
        line_total = 0
        # mutable register line_count https://stackoverflow.com/a/15148557
        line_count = [0]
        count_by_register = defaultdict(int)
        self._generate_register_text(sped, version, line_count, count_by_register)

        # agrupa os registros de topo por bloco, preservando a ordem
        blocos = []
        for register_class in top_register_classes:
            bloco = register_class._name[-4:][0].upper()
            if not blocos or blocos[-1][0] != bloco:
                blocos.append((bloco, []))
            blocos[-1][1].append(register_class)

        domain = [("declaration_id", "=", self.id)]
        pular_vazios = self._skip_empty_blocks()
        primeiro = True
        for bloco, register_classes in blocos:
            # a busca leva o dominio da declaracao: o indicador de
            # movimento do bloco enxerga so ESTA escrituracao (sem o
            # dominio, registros de outras declaracoes da base abririam
            # como "com dados" um bloco vazio aqui, e o PVA recusa a
            # importacao)
            registros = [
                register_class.search(domain) for register_class in register_classes
            ]
            tem_dados = any(registros)
            if pular_vazios and not tem_dados and bloco != "0":
                continue
            if not primeiro:
                line_count = [0]
            sped.write(f"\n|{bloco}001|{0 if tem_dados else 1}|")
            count_by_register[f"{bloco}001"] = 1
            line_count[0] += 1
            for registro in registros:
                registro._generate_register_text(
                    sped, version, line_count, count_by_register
                )
            sped.write(f"\n|{bloco}990|{line_count[0] + 1}|")
            count_by_register[f"{bloco}990"] = 1
            line_total += line_count[0] + 1
            primeiro = False

        # totais:
        sped.write("\n|9001|0|")
        count_by_register["9001"] = 1
        count_by_register["9990"] = 1
        count_by_register["9999"] = 1
        count_by_register["9900"] = len(count_by_register.keys()) + 1

        for item in sorted(
            count_by_register.items(), key=lambda r: self._get_alphanum_sequence(r[0])
        ):
            code = item[0]
            num = item[1]
            sped.write(f"\n|9900|{code}|{num}|")
        linhas_bloco_9 = len(count_by_register.keys()) + 3
        sped.write(f"\n|9990|{linhas_bloco_9}|")

        line_total += linhas_bloco_9
        sped.write(f"\n|9999|{line_total}|")
        return sped.getvalue()
