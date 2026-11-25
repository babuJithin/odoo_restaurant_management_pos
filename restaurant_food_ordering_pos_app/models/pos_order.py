import logging
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'restaurant_food_ordering_pos_app.'
PARAM_APP_CONFIG = PARAM_PREFIX + 'app_pos_config_id'
PARAM_TARGET_CONFIG = PARAM_PREFIX + 'app_target_pos_config_id'
PARAM_CART_EXPIRY = PARAM_PREFIX + 'app_cart_expiry_days'

DELIVERY_PRODUCT_CODE = 'Delivery_007'


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # ------------------------------------------------------------------
    # Mobile app fields (declared once; legacy copies live on sale.order)
    # ------------------------------------------------------------------
    is_app_order = fields.Boolean(string="Mobile App Order", index=True, copy=False, readonly=True)
    cart_chekouted = fields.Boolean(default=False, string="Is cart checkout", index=True, copy=False)
    guest_checkout = fields.Boolean(string="Guest Checkout")
    guest_user_id = fields.Integer(string="Guest USER id", index=True)
    delivery_date = fields.Date(string="Delivery date")
    transaction_id = fields.Char(string="Payment Reference")
    order_platform = fields.Selection([('web', 'Website'), ('Android', 'Android'), ('ios', 'IOS')], 'Order platform')
    payment_type = fields.Selection([('card', 'Card'), ('COD', 'Cash on Delivery'), ('online', 'Online')],
                                    'Payment type')
    marketplace_state = fields.Selection(
        [("new", "Waiting"), ("approved", "Accepted"), ("processing", "Preparing"), ("shipped", "On the way"),
         ("delivered", "Delivered"), ("cancel", "Cancelled")], string="App Order Status",
        default="new", copy=False, tracking=True)
    payment_method = fields.Many2one('payment.type', string="App Payment Type")
    home_delivery_type = fields.Many2one('home.delivery.type', string="Home Delivery Type")
    vehicle_details = fields.Char(string="Vehicle Details")
    cart_zone = fields.Many2one('zone.location', string="Zone")
    latitude = fields.Float(string='Geo Latitude', digits=(10, 7))
    longitude = fields.Float(string='Geo Longitude', digits=(10, 7))
    partner_shipping_id = fields.Many2one('res.partner', string="Delivery Address")
    carrier_id = fields.Many2one('delivery.carrier', string="Delivery Method")

    # ------------------------------------------------------------------
    # POS UI: never expose app carts that are not checked out yet
    # ------------------------------------------------------------------
    @api.model
    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data, config)
        return Domain(domain) & Domain(['|', ('is_app_order', '=', False), ('cart_chekouted', '=', True)])

    def mark_deleted(self):
        """Delete app carts. Draft pos.order unlink is allowed (it cancels then deletes)."""
        self.unlink()

    # ------------------------------------------------------------------
    # Dedicated "Mobile App" point of sale
    # ------------------------------------------------------------------
    @api.model
    def _get_app_config(self, create=True):
        ICP = self.env['ir.config_parameter'].sudo()
        config_id = ICP.get_param(PARAM_APP_CONFIG)
        config = self.env['pos.config'].sudo().browse(int(config_id)).exists() if config_id else False
        if config and config.active:
            return config
        if not create:
            return self.env['pos.config']
        return self._app_ensure_mobile_config()

    @api.model
    def _app_ensure_mobile_config(self):
        """Return (and create when missing) the dedicated "Mobile App" pos.config."""
        ICP = self.env['ir.config_parameter'].sudo()
        PosConfig = self.env['pos.config'].sudo()
        config_id = ICP.get_param(PARAM_APP_CONFIG)
        config = PosConfig.browse(int(config_id)).exists() if config_id else PosConfig
        if config and config.active:
            return config
        company = self.env.company
        config = PosConfig.create({
            'name': _('Mobile App'),
            'company_id': company.id,
            'module_pos_restaurant': False,
        })
        bank_journal = self.env['account.journal'].sudo().search([
            *self.env['account.journal']._check_company_domain(company),
            ('type', '=', 'bank'),
        ], limit=1)
        if bank_journal:
            online_method = self.env['pos.payment.method'].sudo().create({
                'name': _('Mobile App - Card / Online'),
                'journal_id': bank_journal.id,
                'company_id': company.id,
            })
            config.payment_method_ids = [(4, online_method.id)]
            self.env['payment.type'].sudo().search([
                ('type', 'in', ('card', 'online')), ('pos_payment_method_id', '=', False),
            ]).write({'pos_payment_method_id': online_method.id})
        ICP.set_param(PARAM_APP_CONFIG, config.id)
        return config

    @api.model
    def _app_install_mobile_config(self):
        """Called from data XML at install/upgrade. Never blocks the installation: if the
        company has no chart of accounts yet, the config is created lazily on the first API call."""
        try:
            with self.env.cr.savepoint():
                self._app_ensure_mobile_config()
        except Exception as e:  # noqa: BLE001
            _logger.warning("Mobile App point of sale not created at install (will be created on first use): %s", e)

    @api.model
    def _app_find_open_session(self, config):
        return self.env['pos.session'].sudo().search([
            ('config_id', '=', config.id),
            ('state', '!=', 'closed'),
            ('rescue', '=', False),
        ], order='id desc', limit=1)

    @api.model
    def _get_app_session(self):
        """Open session of the Mobile App pos.config; opened automatically when none exists."""
        config = self._get_app_config()
        session = self._app_find_open_session(config)
        if session:
            self._app_open_session(session)
            if session.state == 'opened':
                return session
            raise UserError(_("The Mobile App point of sale is being closed, please retry in a moment."))
        responsible = self.env.ref('base.user_admin', raise_if_not_found=False)
        try:
            with self.env.cr.savepoint():
                session = self.env['pos.session'].sudo().create({
                    'config_id': config.id,
                    'user_id': responsible.id if responsible else SUPERUSER_ID,
                })
        except ValidationError:
            # another request opened the session concurrently
            session = self._app_find_open_session(config)
            if not session:
                raise
        self._app_open_session(session)
        # app orders always update the stock in real time
        if session.update_stock_at_closing:
            session.update_stock_at_closing = False
        return session

    @api.model
    def _app_open_session(self, session):
        """Bring a session from 'opening_control' to 'opened' (Odoo 19 only switches the state in
        set_opening_control(), normally called by the POS UI opening popup)."""
        if session.state == 'opening_control':
            session.action_pos_session_open()
            session.set_opening_control(session.cash_register_balance_start or 0, '')

    # ------------------------------------------------------------------
    # Carts
    # ------------------------------------------------------------------
    @api.model
    def _get_app_cart(self, partner, cart_id=None, guest=None):
        """Single entry point returning the draft, not checked-out app cart of a customer."""
        partner_id = partner.id if isinstance(partner, models.BaseModel) else partner
        if not partner_id:
            return self.browse()
        domain = [
            ('partner_id', '=', int(partner_id)),
            ('is_app_order', '=', True),
            ('cart_chekouted', '=', False),
            ('state', '=', 'draft'),
        ]
        if guest:
            # guests all share the public partner: keep each guest on its own cart
            domain.append(('guest_user_id', '=', guest.id))
        if cart_id:
            try:
                domain.append(('id', '=', int(cart_id)))
            except (TypeError, ValueError):
                return self.browse()
        return self.sudo().search(domain, order='id desc', limit=1)

    @api.model
    def _app_create_cart(self, partner, guest=None):
        session = self._get_app_session()
        partner = self.env['res.partner'].sudo().browse(partner.id if isinstance(partner, models.BaseModel) else int(partner))
        vals = {
            'session_id': session.id,
            'partner_id': partner.id,
            'is_app_order': True,
            'cart_chekouted': False,
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        }
        pricelist = partner.property_product_pricelist
        if pricelist and pricelist.currency_id == session.config_id.currency_id:
            vals['pricelist_id'] = pricelist.id
        if guest:
            vals.update({'guest_checkout': True, 'guest_user_id': guest.id})
        return self.sudo().create(vals)

    @api.model
    def _prepare_pos_line_vals(self, order, product, qty):
        """Values of a pos.order.line priced like the POS UI does (pricelist + taxes + fiscal position)."""
        company = order.company_id
        AccountTax = self.env['account.tax']
        taxes = product.taxes_id.filtered_domain(AccountTax._check_company_domain(company))
        if order.pricelist_id:
            price = order.pricelist_id._get_product_price(product, qty or 1.0, currency=order.currency_id)
        else:
            price = product.lst_price
        taxes_after_fp = order.fiscal_position_id.map_tax(taxes)
        price = AccountTax._fix_tax_included_price_company(price, taxes, taxes_after_fp, company)
        tax_res = taxes_after_fp.compute_all(price, order.currency_id, qty, product=product, partner=order.partner_id)
        return {
            'order_id': order.id,
            'product_id': product.id,
            'qty': qty,
            'price_unit': price,
            'discount': 0.0,
            'tax_ids': [(6, 0, taxes.ids)],
            'full_product_name': product.display_name,
            'price_subtotal': tax_res['total_excluded'],
            'price_subtotal_incl': tax_res['total_included'],
        }

    def _app_add_products(self, products_qty):
        """products_qty: iterable of (product.product, qty)."""
        self.ensure_one()
        vals_list = [self._prepare_pos_line_vals(self, product, float(qty)) for product, qty in products_qty]
        lines = self.env['pos.order.line'].sudo().create(vals_list) if vals_list else self.env['pos.order.line']
        self._app_recompute(lines)
        return lines

    def _app_recompute(self, lines=None):
        """Recompute line subtotals and order totals after any line create/write/unlink."""
        for order in self:
            changed = (lines & order.lines) if lines is not None else order.lines
            changed._onchange_amount_line_all()
            order._compute_prices()

    def _app_get_reference(self):
        """Human order reference: the POS name once assigned, else the receipt number."""
        self.ensure_one()
        if self.name and self.name != '/':
            return self.name
        return self.pos_reference or ''

    def _app_amount_undiscounted(self):
        self.ensure_one()
        return sum(line.price_unit * line.qty for line in self.lines)

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------
    def _app_carrier_price(self, carrier, delivery_lines):
        self.ensure_one()
        goods = self.lines - delivery_lines
        total = sum(goods.mapped('price_subtotal_incl'))
        if carrier.free_over and self.currency_id.compare_amounts(total, carrier.amount) >= 0:
            return 0.0
        if carrier.delivery_type == 'fixed':
            return carrier.fixed_price
        if carrier.delivery_type == 'base_on_rule':
            weight = sum(line.product_id.weight * line.qty for line in goods)
            volume = sum(line.product_id.volume * line.qty for line in goods)
            quantity = sum(goods.mapped('qty'))
            try:
                return carrier._get_price_from_picking(total, weight, volume, quantity)
            except UserError as e:
                _logger.warning("Carrier %s has no rule for app order %s: %s", carrier.name, self.id, e)
                return 0.0
        return carrier.product_id.lst_price

    def _app_add_delivery_line(self, carrier):
        """Replacement of sale.order._check_carrier_quotation(): the carrier product is added as a
        normal POS line at the carrier price."""
        self.ensure_one()
        if not carrier or not carrier.product_id:
            return self.env['pos.order.line']
        product = carrier.product_id
        delivery_lines = self.lines.filtered(
            lambda l: l.product_id == product or l.product_id.default_code == DELIVERY_PRODUCT_CODE)
        price = self._app_carrier_price(carrier, delivery_lines)
        delivery_lines.unlink()
        vals = self._prepare_pos_line_vals(self, product, 1.0)
        vals['price_unit'] = price
        line = self.env['pos.order.line'].sudo().create(vals)
        self.carrier_id = carrier
        self._app_recompute(line)
        return line

    def _app_payment_method(self, payment_type_rec):
        """POS payment method to register a card/online payment in the order's config."""
        self.ensure_one()
        allowed = self.config_id.payment_method_ids
        method = payment_type_rec.pos_payment_method_id if payment_type_rec else self.env['pos.payment.method']
        if method and method in allowed:
            return method
        return allowed.filtered(lambda m: m.type == 'bank')[:1]

    def _app_move_to_target_session(self, payment_method=None):
        """Move a checked-out order from the Mobile App session to the restaurant session (if a
        target point of sale is configured and open). Returns True when moved."""
        self.ensure_one()
        target_id = self.env['ir.config_parameter'].sudo().get_param(PARAM_TARGET_CONFIG)
        target = self.env['pos.config'].sudo().browse(int(target_id)).exists() if target_id else False
        if not target or target == self.config_id:
            return False
        session = self._app_find_open_session(target)
        if not session or session.state != 'opened':
            return False
        if payment_method and payment_method not in target.payment_method_ids:
            _logger.info("App order %s kept in Mobile App session: payment method %s not in %s",
                         self.id, payment_method.name, target.name)
            return False
        self.session_id = session
        return True

    def _app_delivery_preset(self):
        """'Delivery' POS preset (identification = address) for this order's point of sale.
        Prefers a preset enabled on the order's config, then any address preset, then the
        pos_restaurant default 'Delivery' preset."""
        self.ensure_one()
        config = self.config_id
        presets = config.available_preset_ids | config.default_preset_id
        preset = presets.filtered(lambda p: p.identification == 'address' and not p.is_return)[:1]
        if not preset:
            preset = self.env['pos.preset'].sudo().search(
                [('identification', '=', 'address'), ('is_return', '=', False)], limit=1)
        if not preset:
            preset = self.env.ref('pos_restaurant.pos_delivery_preset', raise_if_not_found=False)
        return preset or self.env['pos.preset']

    def _app_set_delivery(self, address):
        """Mark the app order as a home delivery to the given address.
        The POS 'Delivery' preset requires the order customer to have a street, so the delivery
        address (a child contact of the app user) becomes the order customer. Lookups by app user
        must therefore use ('partner_id', 'child_of', user.partner_id)."""
        self.ensure_one()
        vals = {'partner_shipping_id': address.id, 'partner_id': address.id}
        preset = self._app_delivery_preset()
        if preset:
            vals['preset_id'] = preset.id
        self.write(vals)

    def _app_cod_payment_method(self, payment_type_rec):
        """POS payment method to pre-fill for Cash on Delivery orders."""
        self.ensure_one()
        allowed = self.config_id.payment_method_ids
        method = payment_type_rec.pos_payment_method_id if payment_type_rec else self.env['pos.payment.method']
        if method and method in allowed:
            return method
        return allowed.filtered(lambda m: m.is_cash_count)[:1]

    def _app_prefill_payment(self, payment_method):
        """Add the payment line chosen in the app WITHOUT finalising the order: the POS shows it
        on the payment screen and the cashier only validates once the order is delivered/paid."""
        self.ensure_one()
        amount = self._get_rounded_amount(self.amount_total)
        if not payment_method or self.currency_id.is_zero(amount) or self.payment_ids:
            return
        self.env['pos.payment'].sudo().create({
            'pos_order_id': self.id,
            'amount': amount,
            'payment_method_id': payment_method.id,
        })

    def _app_register_payment(self, payment_method, transaction_id=None):
        """Register the card/online payment captured by the app. The order is NOT finalised: it
        stays open in the POS until the cashier marks it delivered (see _app_finalize)."""
        self.ensure_one()
        amount = self._get_rounded_amount(self.amount_total)
        if not self.currency_id.is_zero(amount):
            self.env['pos.payment'].sudo().create({
                'pos_order_id': self.id,
                'amount': amount,
                'payment_method_id': payment_method.id,
                'transaction_id': transaction_id or False,
                'payment_ref_no': transaction_id or False,
                'payment_status': 'done',
            })
        self.amount_paid = self._compute_amount_paid()

    def _app_finalize(self):
        """Mark the order paid and deliver the goods, like the POS payment screen does."""
        self.ensure_one()
        self.amount_paid = self._compute_amount_paid()
        self.action_pos_order_paid()
        self._create_order_picking()
        self._compute_total_cost_in_real_time()

    # ------------------------------------------------------------------
    # App order status (driven by the POS cashier)
    # ------------------------------------------------------------------
    APP_STATUS_FLOW = ['new', 'approved', 'processing', 'shipped', 'delivered']

    def action_pos_order_paid(self):
        res = super().action_pos_order_paid()
        # paid from the POS payment screen (e.g. cash collected at the door) = delivered
        for order in self:
            if order.is_app_order and order.cart_chekouted and order.marketplace_state not in ('delivered', 'cancel'):
                order.marketplace_state = 'delivered'
        return res

    def app_pos_set_status(self, new_state, config_id=False):
        """Called from the POS: move checked-out app orders to the given status.
        Cancel is only allowed while the order is still waiting; payments captured by the app are
        then removed from the order and must be refunded manually with the payment provider."""
        flow = self.APP_STATUS_FLOW
        for order in self.sudo():
            if not (order.is_app_order and order.cart_chekouted):
                raise UserError(_("Order %s is not a mobile app order.", order.display_name))
            if order.state != 'draft' or order.marketplace_state in ('delivered', 'cancel'):
                raise UserError(_("Order %s is already closed.", order.display_name))
            current = order.marketplace_state or 'new'
            if new_state == 'cancel':
                if current != 'new':
                    raise UserError(_("Only waiting orders can be cancelled (order %s is %s).",
                                      order.display_name,
                                      dict(order._fields['marketplace_state'].selection).get(current)))
                paid = order.payment_ids.filtered(lambda p: p.payment_status == 'done')
                if paid:
                    order.message_post(body=_(
                        "Order cancelled from the POS. Refund %(amount)s manually (transaction %(tx)s).",
                        amount=sum(paid.mapped('amount')), tx=order.transaction_id or '-'))
                order.payment_ids.unlink()
                order.amount_paid = 0.0
                order.marketplace_state = 'cancel'
                order.action_pos_order_cancel()
                continue
            if new_state not in flow or flow.index(new_state) != flow.index(current) + 1:
                raise UserError(_("Order %s cannot go from %s to %s.", order.display_name, current, new_state))
            if new_state == 'delivered':
                if order.currency_id.compare_amounts(order._compute_amount_paid(),
                                                     order._get_rounded_amount(order.amount_total)) < 0:
                    raise UserError(_("Order %s is not fully paid: open it and register the payment.",
                                      order.display_name))
                order._app_finalize()  # also sets marketplace_state = delivered
            else:
                order.marketplace_state = new_state
        for config in self.config_id:
            if config.current_session_id:
                config.notify_synchronisation(config.current_session_id.id,
                                              self.env.context.get('device_identifier', 0))
        config = self.env['pos.config'].browse(config_id).exists() if config_id else self.config_id[:1]
        return self.read_pos_data({}, config)

    def _app_send_confirmation_mail(self):
        self.ensure_one()
        template = self.env.ref('restaurant_food_ordering_pos_app.mail_template_app_pos_order',
                                raise_if_not_found=False)
        email = self.email or self.partner_shipping_id.email or self.partner_id.email
        if not template or not email:
            return False
        template.sudo().send_mail(self.id, force_send=False, email_values={'email_to': email})
        return True

    def _app_notify_pos(self):
        """Push checked-out app orders to the open POS screens and the kitchen display."""
        for order in self:
            order._send_order()  # hook used by the preparation (kitchen) display modules
        for config in self.config_id:
            session = config.current_session_id
            if not session:
                continue
            config.notify_synchronisation(session.id, self.env.context.get('device_identifier', 0))
            config._notify('ORDER_STATE_CHANGED', {})


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _app_carryover_orders(self):
        """App orders of this session that must not block its closing: carts that were never
        checked out and, in the Mobile App point of sale, unpaid (COD) orders."""
        if not self.ids:
            return self.env['pos.order']
        orders = self.env['pos.order'].sudo().search([
            ('session_id', 'in', self.ids),
            ('state', '=', 'draft'),
            ('is_app_order', '=', True),
        ])
        app_config = self.env['pos.order']._get_app_config(create=False)
        return orders.filtered(lambda o: not o.cart_chekouted or (app_config and o.config_id == app_config))

    def get_session_orders(self):
        return super().get_session_orders() - self._app_carryover_orders()

    def _check_if_no_draft_orders(self):
        # get_session_orders() already ignores carried-over app orders; explicit here so that the
        # behaviour does not depend on how the core check gathers the orders.
        draft_orders = self.get_session_orders().filtered(lambda order: order.state == 'draft')
        if draft_orders:
            return super()._check_if_no_draft_orders()
        return True

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        carry = self._app_carryover_orders()
        res = super()._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)
        if carry and self.state == 'closed':
            self._app_carry_over(carry)
        return res

    def _app_carry_over(self, orders):
        """Cancel abandoned carts (older than the configured expiry) and move the others to the
        open session of the Mobile App point of sale (re-opened automatically)."""
        days = int(self.env['ir.config_parameter'].sudo().get_param(PARAM_CART_EXPIRY, 0) or 0)
        if days > 0:
            limit = fields.Datetime.now() - timedelta(days=days)
            stale = orders.filtered(lambda o: not o.cart_chekouted and o.write_date and o.write_date < limit)
            if stale:
                stale.action_pos_order_cancel()
                orders -= stale
        if orders:
            session = self.env['pos.order']._get_app_session()
            orders.sudo().write({'session_id': session.id})
            _logger.info("Carried %s mobile app order(s) over to session %s", len(orders), session.name)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    app_pos_config_id = fields.Many2one(
        'pos.config', string="Mobile App Point of Sale", config_parameter=PARAM_APP_CONFIG,
        help="Point of sale holding the mobile app carts and orders. Created automatically when empty.")
    app_target_pos_config_id = fields.Many2one(
        'pos.config', string="Send App Orders To", config_parameter=PARAM_TARGET_CONFIG,
        help="Restaurant point of sale that receives app orders at checkout (when it has an open "
             "session). Leave empty to keep the orders in the Mobile App point of sale.")
    app_cart_expiry_days = fields.Integer(
        string="Cancel Abandoned Carts After (days)", config_parameter=PARAM_CART_EXPIRY,
        help="When the Mobile App session is closed, carts not modified for this number of days are "
             "cancelled; the others move to the next session. 0 = never cancel.")
