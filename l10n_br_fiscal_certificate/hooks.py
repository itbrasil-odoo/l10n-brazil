# Copyright (C) 2021 - Luis Felipe Mileo - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import logging
import warnings

# signxml<5 imports OpenSSL.crypto.verify, deprecated by pyOpenSSL, so every
# Odoo process logs a DeprecationWarning the first time signxml is imported.
# This is that first import. There is nothing to fix on our side: signxml>=5
# needs cryptography>=45 and Odoo 18 pins 42.
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"verify\(\) is deprecated",
        category=DeprecationWarning,
    )
    from erpbrasil.assinatura import misc

from odoo import _

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    def prepare_fake_certificate_vals(
        valid=True,
        passwd="123456",
        issuer="EMISSOR A TESTE",
        country="BR",
        subject="CERTIFICADO VALIDO TESTE",
    ):
        return {
            "scope": "l10n_br",
            "pkcs12_password": passwd,
            "content": misc.create_fake_certificate_file(
                valid, passwd, issuer, country, subject
            ),
        }

    env.cr.execute(
        "select demo from ir_module_module where name='l10n_br_fiscal_certificate';"
    )
    if env.cr.fetchone()[0]:
        companies = [
            env.ref("base.main_company", raise_if_not_found=False),
            env.ref("l10n_br_base.empresa_simples_nacional", raise_if_not_found=False),
            env.ref("l10n_br_base.empresa_lucro_presumido", raise_if_not_found=False),
            env.ref("l10n_br_base.empresa_lucro_real", raise_if_not_found=False),
        ]
        try:
            certificate_model = env["certificate.certificate"]
            for company in companies:
                if not company:
                    continue
                vals = prepare_fake_certificate_vals()
                vals["company_id"] = company.id
                company.certificate_id = certificate_model.create(vals)
        except NameError:  # (means from erpbrasil.assinatura import misc failed)
            _logger.error(
                _(
                    "Python Library erpbrasil.assinatura not installed!"
                    "You can install it later with: pip install erpbrasil.assinatura."
                    "Demo companies fake A1 certificates were not created."
                )
            )
