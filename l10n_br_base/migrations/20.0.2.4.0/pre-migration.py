# Copyright 2026 - TODAY ITBrasil (<https://itbrasil.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Plain SQL on purpose: this script must run even where openupgradelib is not
# installed, and it has to read res_bank, which has no model anymore in 20.0.

import logging

_logger = logging.getLogger(__name__)

LEGACY_TABLE = "l10n_br_base_legacy_res_bank"


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s AND relkind = 'r'", (table,))
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _keep_legacy_banks(cr):
    """Keep the Brazilian data of the bank directory.

    Odoo 20.0 removed res.bank; short_name, ispb_number and compe_member have
    no field to go to, so a plain copy of the table is kept for reference.
    """
    if _table_exists(cr, LEGACY_TABLE):
        return
    columns = [
        column
        for column in (
            "id",
            "name",
            "bic",
            "code_bc",
            "short_name",
            "ispb_number",
            "compe_member",
            "active",
        )
        if _column_exists(cr, "res_bank", column)
    ]
    # Custom fields (Studio or manual, always prefixed with x_) hold data that
    # has nowhere else to go either.
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'res_bank' AND column_name LIKE 'x\\_%'
        ORDER BY ordinal_position
        """
    )
    columns += [f'"{row[0]}"' for row in cr.fetchall()]
    cr.execute(  # pylint: disable=sql-injection
        f"CREATE TABLE {LEGACY_TABLE} AS SELECT {', '.join(columns)} FROM res_bank"
    )
    _logger.info("%s bank(s) copied to %s", cr.rowcount, LEGACY_TABLE)


def _move_bank_data_to_accounts(cr):
    """res.bank.code_bc -> res.partner.bank.code_bc (the bank of the account).

    The bank name and BIC are converted by the base upgrade; they are only
    written here on accounts where they are still empty.
    """
    cr.execute(
        "ALTER TABLE res_partner_bank ADD COLUMN IF NOT EXISTS code_bc varchar(3)"
    )
    cr.execute(
        """
        UPDATE res_partner_bank account
        SET code_bc = left(btrim(bank.code_bc), 3)
        FROM res_bank bank
        WHERE bank.id = account.bank_id
          AND account.code_bc IS NULL
          AND nullif(btrim(bank.code_bc), '') IS NOT NULL
        """
    )
    _logger.info("code_bc written on %s bank account(s)", cr.rowcount)
    for column, source in (("bank_name", "name"), ("bank_bic", "bic")):
        if not _column_exists(cr, "res_partner_bank", column):
            continue
        if not _column_exists(cr, "res_bank", source):
            continue
        cr.execute(  # pylint: disable=sql-injection
            f"""
            UPDATE res_partner_bank account
            SET {column} = bank.{source}
            FROM res_bank bank
            WHERE bank.id = account.bank_id
              AND nullif(btrim(account.{column}), '') IS NULL
              AND nullif(btrim(bank.{source}), '') IS NOT NULL
            """
        )
        _logger.info("%s written on %s bank account(s)", column, cr.rowcount)


def migrate(cr, version):
    if not version:
        return
    if not _table_exists(cr, "res_bank"):
        _logger.warning(
            "res_bank is already gone: the Brazilian bank code (code_bc) of the "
            "bank accounts could not be recovered and must be filled in again."
        )
        return
    _keep_legacy_banks(cr)
    if not _column_exists(cr, "res_bank", "code_bc"):
        return
    if not _column_exists(cr, "res_partner_bank", "bank_id"):
        _logger.warning(
            "res_partner_bank.bank_id is already gone: code_bc was not written "
            "on the bank accounts; the bank directory is kept in %s.",
            LEGACY_TABLE,
        )
        return
    _move_bank_data_to_accounts(cr)
