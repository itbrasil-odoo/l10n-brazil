# License AGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html).

from datetime import date, datetime

from odoo.tests import common

from odoo.addons.l10n_br_sped_base.models.sped_declaration import period_bounds_utc


class TestPeriodBounds(common.TransactionCase):
    """The period is a range of local calendar days over a UTC Datetime."""

    def test_month_in_brasilia_time(self):
        self.env.user.tz = "America/Sao_Paulo"
        start, end = period_bounds_utc(self.env, date(2026, 9, 1), date(2026, 9, 30))
        # 01/09 00:00 BRT is 03:00 UTC; the end is exclusive and covers the
        # whole of 30/09, including its evening (already 01/10 in UTC)
        self.assertEqual(start, datetime(2026, 9, 1, 3, 0))
        self.assertEqual(end, datetime(2026, 10, 1, 3, 0))

    def test_user_without_timezone_falls_back_to_brasilia(self):
        self.env.user.tz = False
        start, _end = period_bounds_utc(self.env, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(start, datetime(2026, 9, 1, 3, 0))

