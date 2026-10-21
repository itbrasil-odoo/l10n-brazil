# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # country_id was stored on hr_employee, shadowing the hr.version field.
    # Keep the values on the versions before dropping the orphan column.
    if openupgrade.column_exists(env.cr, "hr_employee", "country_id"):
        openupgrade.logged_query(
            env.cr,
            """
            UPDATE hr_version v
               SET country_id = e.country_id
              FROM hr_employee e
             WHERE v.employee_id = e.id
               AND e.country_id IS NOT NULL
               AND v.country_id IS NULL
            """,
        )
        openupgrade.drop_columns(env.cr, [("hr_employee", "country_id")])
