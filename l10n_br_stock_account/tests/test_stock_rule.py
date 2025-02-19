# Copyright (C) 2019-Today - Akretion (<http://www.akretion.com>).
# @author Magno Costa <magno.costa@akretion.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import Form, TransactionCase
from odoo.tools import mute_logger


class StockRuleTest(TransactionCase):
    """Test Stock Rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a product route containing a stock rule that will
        # generate a move from Stock for every procurement created in Output
        cls.product_route = cls.env["stock.route"].create(
            {
                "name": "Stock -> output route",
                "product_selectable": True,
                "rule_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Stock -> output rule",
                            "action": "pull",
                            "picking_type_id": cls.env.ref(
                                "stock.picking_type_internal"
                            ).id,
                            "location_src_id": cls.env.ref(
                                "stock.stock_location_stock"
                            ).id,
                            "location_dest_id": cls.env.ref(
                                "stock.stock_location_output"
                            ).id,
                            "invoice_state": "2binvoiced",
                            "fiscal_operation_id": cls.env.ref(
                                "l10n_br_fiscal.fo_venda"
                            ).id,
                        },
                    )
                ],
            }
        )

        # Set this route on `product.product_product_3`
        cls.env.ref("product.product_product_3").write(
            {"route_ids": [(4, cls.product_route.id)]}
        )

    def test_procument_order(self):
        """Test Stock Rule create stock.move with Fiscal fields."""
        # Create Delivery Order of 10 `product.product_product_3`
        # from Output -> Customer
        product = self.env.ref("product.product_product_3")
        vals = {
            "name": "Delivery order for procurement",
            "partner_id": self.ref("base.res_partner_2"),
            "picking_type_id": self.ref("stock.picking_type_out"),
            "location_id": self.ref("stock.stock_location_output"),
            "location_dest_id": self.ref("stock.stock_location_customers"),
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": "/",
                        "product_id": product.id,
                        "product_uom": product.uom_id.id,
                        "product_uom_qty": 10.00,
                        "procure_method": "make_to_order",
                        "location_id": self.ref("stock.stock_location_output"),
                        "location_dest_id": self.ref("stock.stock_location_customers"),
                    },
                )
            ],
        }
        pick_output = self.env["stock.picking"].create(vals)

        # Confirm delivery order.
        pick_output.action_confirm()

        # I run the scheduler.
        # Note: If purchase if already installed, the method _run_buy
        # will be called due to the purchase demo data. As we update the
        # stock module to run this test, the method won't be an attribute
        # of stock.procurement at this moment. For that reason we mute the
        # logger when running the scheduler.
        with mute_logger("odoo.addons.stock.models.procurement"):
            self.env["procurement.group"].run_scheduler()

        # Check that a picking was created from stock to output.
        moves = self.env["stock.move"].search(
            [
                ("product_id", "=", self.ref("product.product_product_3")),
                ("location_id", "=", self.ref("stock.stock_location_stock")),
                ("location_dest_id", "=", self.ref("stock.stock_location_output")),
                ("move_dest_ids", "in", [pick_output.move_ids[0].id]),
            ]
        )
        self.assertEqual(
            len(moves.ids),
            1,
            "It should have created a picking from Stock to Output with the"
            " original picking as destination",
        )

        # Check if the fields included in l10n_br_stock_account was copied to move
        for move in moves:
            self.assertEqual(
                move.invoice_state,
                "2binvoiced",
                "The stock.move created has not invoice_state field 2binvoiced",
            )
            self.assertEqual(
                move.fiscal_operation_id.name,
                "Venda",
                "The stock.move created has not operation_id field Venda",
            )
            # self.assertEqual(
            #     move.fiscal_operation_line_id.name, 'Venda',
            #     "The stock.move created has not operation_line_id field Venda")

    def test_stock_rule(self):
        """Test Stock Rule"""
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        reception_route = warehouse.reception_route_id
        reception_route.rule_ids.action_archive()
        stock_rule_form = Form(self.env["stock.rule"])
        stock_rule_form.name = "Looping Rule"
        stock_rule_form.route_id = reception_route
        stock_rule_form.location_dest_id = warehouse.lot_stock_id
        stock_rule_form.location_src_id = warehouse.lot_stock_id
        stock_rule_form.action = "pull_push"
        stock_rule_form.procure_method = "make_to_order"
        stock_rule_form.picking_type_id = warehouse.int_type_id
        stock_rule_form.save()
