# Copyright 2016 KMEE INFORMATICA LTDA (https://kmee.com.br)
# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Ponto de venda adaptado à legislação brasileira",
    "summary": "Operação fiscal na venda de balcão, para que a fatura gerada "
    "pelo PDV seja um documento fiscal válido",
    "version": "18.0.1.1.0",
    "category": "Localization/Brazil",
    "license": "AGPL-3",
    "author": "KMEE, IT Brasil, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-brazil",
    "development_status": "Alpha",
    "depends": [
        "l10n_br_account",
        "point_of_sale",
    ],
    "data": [
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
    ],
    "installable": True,
}
