# Copyright 2018 Akretion
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "SPED - EFD ICMS IPI",
    "summary": """
        Arquivo EFD ICMS IPI do SPED / SPED Fiscal""",
    "version": "18.0.1.6.5",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Alpha",
    "maintainers": ["rvalyi", "renatonlima"],
    "depends": [
        "l10n_br_sped_base",
        "l10n_br_account",
        "l10n_br_tax_assessment",
        # e-document states (autorizada, denegada...) live here in the
        # refactored l10n_br_fiscal
        "l10n_br_fiscal_edi",
        "stock_account",
    ],
    "external_dependencies": {
        "python": [
            "erpbrasil-base>=2.4.2",
        ]
    },
    "data": [
        "security/ir.model.access.csv",
        "views/sped_efd_icms_ipi.xml",
        "views/obligation.xml",
    ],
    "demo": [],
    "application": True,
    "post_init_hook": "post_init_hook",
}
