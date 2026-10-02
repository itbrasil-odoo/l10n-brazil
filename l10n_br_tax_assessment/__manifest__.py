# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Apuração de Impostos sobre Consumo (Brasil)",
    "summary": "Conta gráfica mensal de ICMS, IPI, PIS e COFINS",
    "version": "18.0.1.0.2",
    "category": "Localization/Brazil",
    "license": "AGPL-3",
    "author": "KMEE, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Beta",
    "maintainers": ["mileo"],
    "depends": [
        "l10n_br_account",
        "account_tax_balance",
    ],
    "data": [
        "security/tax_assessment_security.xml",
        "security/ir.model.access.csv",
        "views/tax_assessment_views.xml",
    ],
    # The demo (invoices and the assessments computed from them) is loaded by
    # the hook, not from here: it needs the demo company active and its chart
    # loaded, and in 18.0 the tax groups it assesses only exist per company.
    "post_init_hook": "post_init_hook",
    "installable": True,
}
