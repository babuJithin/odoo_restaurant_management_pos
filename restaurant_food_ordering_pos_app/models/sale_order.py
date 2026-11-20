import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Legacy storage of mobile-app orders.

    New app carts/orders are stored as ``pos.order`` (see pos_order.py). These fields are kept
    (declared once, here) only so that historic app orders stay readable and keep showing in
    /api/v1/orderHistory during the transition.
    """
    _inherit = 'sale.order'

    guest_checkout = fields.Boolean(string="Guest Checkout")
    guest_user_id = fields.Integer(string="Guest USER id")
    delivery_date = fields.Date(string="Delivery date")
    transaction_id = fields.Char(string="Payment Reference")
    order_platform = fields.Selection([('web', 'Website'), ('Android', 'Android'), ('ios', 'IOS')], 'Order platform')
    payment_type = fields.Selection([('card', 'Card'), ('COD', 'Cash on Delivery'), ('online', 'Online')],
                                    'Payment type')
    client_order_ref = fields.Char('Order Note')
    marketplace_state = fields.Selection(
        [("new", "New"), ("approved", "Approved"), ("processing", "Processing"), ("shipped", "Shipped"),
         ("delivered", "Delivered"), ("cancel", "Cancelled")], default="new", copy=False, tracking=True)
    cart_chekouted = fields.Boolean(default=False, string="Is cart checkout")
    home_delivery_type = fields.Many2one('home.delivery.type', string="Home Delivery Type")
    payment_method = fields.Many2one('payment.type', string="Payment Type")
    vehicle_details = fields.Char(string="Vehicle Details")
    cart_zone = fields.Many2one('zone.location', string="Zone")
    latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
    longitude = fields.Float(string='Geo Longitude', digits=(10, 7))

    def mark_deleted(self):
        self.unlink()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_note = fields.Char(string="Product Description")
