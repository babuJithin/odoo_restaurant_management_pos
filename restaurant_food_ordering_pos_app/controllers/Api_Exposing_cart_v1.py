import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Keys returned per cart line, per endpoint (kept exactly as the app receives them today).
SUMMARY_LINE_KEYS = ('id', 'product_type_id', 'product_name', 'product_id', 'quantity', 'qes_quantity',
                     'max_allowed_qty', 'product_uom', 'product_uom_id', 'max_product_qty', 'product_packaging',
                     'price', 'delivery_methods', 'image', 'sub_total', 'product_note')
VIEW_LINE_KEYS = ('id', 'product_type_id', 'product_name', 'product_id', 'brand', 'quantity', 'qes_quantity',
                  'max_allowed_qty', 'product_uom', 'product_uom_id', 'inventory_availability', 'price',
                  'delivery_methods', 'image', 'sub_total', 'product_note')
CREATE_LINE_KEYS = ('id', 'product_type_id', 'product_name', 'product_id', 'quantity', 'qes_quantity',
                    'inventory_availability', 'price', 'delivery_methods', 'image', 'sub_total', 'product_note')
UPDATE_LINE_KEYS = ('id', 'product_type_id', 'product_name', 'product_id', 'quantity', 'qes_quantity',
                    'max_allowed_qty', 'product_uom', 'product_uom_id', 'inventory_availability', 'price',
                    'image', 'sub_total', 'product_note')


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _resolve_customer(data, uid_key='uid'):
    """Return (partner_id, guest_session, error_dict) for the app user / guest in the request."""
    Guest = request.env['guest.session'].sudo()
    uid = _to_int(data.get(uid_key))
    if data.get('is_guest') == "true":
        guest = Guest.search([('id', '=', uid)]) if uid else Guest
        if not guest:
            return False, Guest, {'status': False, 'message': 'You are not a Valid user'}
        public_user = request.env['res.users'].sudo().get_res_user_public()
        return public_user.partner_id.id, guest, None
    partner_id = request.env['res.users'].sudo().search([('id', '=', uid)]).partner_id.id if uid else False
    return partner_id, Guest, None


def _line_info(line, keys):
    product = line.product_id
    template = product.product_tmpl_id
    info = {
        'id': line.id or 0,
        'product_type_id': product.id or 0,
        'product_name': product.display_name or "",
        'product_id': template.id or 0,
        'brand': product.brand_id.name or "" if 'brand_id' in product._fields else "",
        'quantity': line.qty or 0,
        'qes_quantity': line.qty or 0,
        'max_allowed_qty': product.virtual_available if product.virtual_available > 0.0 else 0.0,
        'product_uom': product.uom_id.name if product.uom_id else "",
        'product_uom_id': product.uom_id.id if product.uom_id else 0,
        'max_product_qty': 0,
        'product_packaging': [],
        'inventory_availability': "always",
        # line price everywhere (summary already used it; view/create/update used list_price)
        'price': round(line.price_unit, 2) or 0,
        'delivery_methods': [],
        'image': "http://" + str(request.httprequest.host) + "/website/image/product.template/{}/image_1920".format(
            template.id) if template.image_1920 else "False",
        'sub_total': round(line.price_subtotal, 2) or 0,
        'product_note': template.product_note or "",
    }
    return {key: info[key] for key in keys}


def _lines_info(order, keys):
    return [_line_info(line, keys) for line in order.lines]


def _cart_dict(order, keys):
    """Equivalent of the former sale.order search_read() row."""
    values = {
        'id': order.id,
        'name': order._app_get_reference(),
        'order_line': order.lines.ids,
        'amount_total': order.amount_total,
        'amount_undiscounted': order._app_amount_undiscounted(),
    }
    return {key: values[key] for key in ('id',) + tuple(keys)}


def _products_qty(products_info):
    """[(product.product, qty)] from the products_info payload, or None if a product is invalid."""
    result = []
    for item in products_info or []:
        product = request.env['product.product'].sudo().search([('id', '=', _to_int(item.get('product_type_id')))])
        if not product:
            return None
        result.append((product, float(item.get('quantity') or 0)))
    return result


class Api_Exposing_Cartv1(http.Controller):

    @http.route('/api/v1/cart/summary', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_summary_v1(self, **data):
        data = http.request.get_json_data() or data
        customer_id, guest, error = _resolve_customer(data)
        if error:
            return error
        if not customer_id:
            return ({'status': False, 'message': 'Your Cusomer id dont exist', 'id_code': 404})
        PosOrder = request.env['pos.order'].sudo()
        cart = PosOrder._get_app_cart(customer_id, guest=guest)
        if not cart:
            return ({'status': False, 'message': 'Cant find a cart for customer with given Id', 'id_code': 404})
        try:
            carts1 = [_cart_dict(cart, ('order_line', 'amount_total', 'name'))]
            cart_lines_info = _lines_info(cart, SUMMARY_LINE_KEYS)
            return {'status': True, 'message': 'Your Cart Summary Details:', 'cart': carts1, 'lines': cart_lines_info}
        except Exception as e:
            _logger.exception("cart/summary failed: %s", e)
            return ({'status': False, 'message': 'Please Pass Correct Valuesyyy', 'id_code': 404})

    @http.route('/api/v1/cart/view', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_view_v1(self, **data):
        data = http.request.get_json_data() or data
        customer_id, guest, error = _resolve_customer(data)
        if error:
            return error
        if not customer_id:
            return ({'status': False, 'message': 'Please Pass Correct Customer Id', 'id_code': 404})
        try:
            cart = request.env['pos.order'].sudo()._get_app_cart(
                customer_id, cart_id=_to_int(data.get('cart_id')), guest=guest)
            if not cart:
                return ({'status': False, 'message': 'Please Pass Correct Cart info', 'id_code': 404})
            live_carts = {
                "id": cart.id,
                "name": cart._app_get_reference(),
                "order_line": cart.lines.ids,
                "amount_without_discount": round(cart._app_amount_undiscounted(), 2),
                "amount_total": round(cart.amount_total, 2),
            }
            live_cart_info = [live_carts]
            cart_lines_info = _lines_info(cart, VIEW_LINE_KEYS)
            if cart_lines_info:
                return {'status': True, 'message': 'Your Cart Summary Details:', 'cart': live_cart_info,
                        'lines': cart_lines_info}
            return {'status': False, 'message': 'Your Cart Is Empty', 'cart': live_cart_info,
                    'lines': cart_lines_info}
        except Exception as e:
            _logger.exception("cart/view failed: %s", e)
            return ({'status': False, 'message': 'Please Pass Correct Cart info', 'id_code': 404})

    # add cart create seperate api   pass product ID uom ID and quantity in product info dictionary
    @http.route('/api/v1/cart/create', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_live_create_v1(self, **data):
        data = http.request.get_json_data() or data
        customer_id, guest, error = _resolve_customer(data)
        if error:
            return error
        if not customer_id:
            return ({'status': False, 'message': 'You are not a Valid user'})
        try:
            if not data.get('cart_id') and not data.get('line_id'):
                products_qty = _products_qty(data.get('products_info'))
                if products_qty is None:
                    return {"status": False, "message": "Please pass Product Variant ID"}
                PosOrder = request.env['pos.order'].sudo()
                cart = PosOrder._get_app_cart(customer_id, guest=guest)
                if not cart:
                    cart = PosOrder._app_create_cart(customer_id, guest=guest)
                elif guest:
                    cart.write({'guest_checkout': True, 'guest_user_id': guest.id})
                cart._app_add_products(products_qty)
                if cart:
                    cart_info = [{
                        'id': cart.id,
                        'order_line': cart.lines.ids,
                        'amount_total': cart.amount_total,
                        'name': cart._app_get_reference(),
                    }]
                    return ({'status': True, 'message': 'Cart Created Successfully', 'cart': cart_info,
                             'lines': _lines_info(cart, CREATE_LINE_KEYS)})
                return ({'status': False, 'message': 'Please pass correct values for the cart creation'})
        except Exception as e:
            _logger.info("enterd in Exception  %s" % str(e))
            return ({'status': False, 'message': 'Please Pass Correct Info', "err": str(e)})

    @http.route('/api/v1/cart/update', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_update_v3(self, **data):
        data = http.request.get_json_data() or data
        customer_id, guest, error = _resolve_customer(data)
        if error:
            return error
        if not customer_id:
            return ({'status': False, 'message': 'You are not a Valid user'})
        PosOrder = request.env['pos.order'].sudo()
        carts_id = PosOrder._get_app_cart(customer_id, cart_id=data.get('cart_id'), guest=guest) \
            if data.get('cart_id') else PosOrder
        try:
            if data.get('line_id'):
                line = request.env['pos.order.line'].sudo().search([('id', '=', _to_int(data.get('line_id')))])
                cart = PosOrder._get_app_cart(customer_id, cart_id=line.order_id.id, guest=guest) if line else PosOrder
                if not line or not cart:
                    return ({'status': False, 'message': 'Please pass correct Line Info', 'id_code': 404})
                quantity = float(data.get('quantity') or 0)
                if quantity != 0:
                    line.write({'qty': quantity})
                    cart._app_recompute(line)
                    carts = [_cart_dict(cart, ('order_line', 'amount_undiscounted', 'amount_total'))]
                    return ({'status': True, 'message': 'Quantity updation is done', 'cart': carts,
                             'lines': _lines_info(cart, UPDATE_LINE_KEYS)})
                line.unlink()
                cart._app_recompute()
                carts = [_cart_dict(cart, ('order_line', 'amount_total'))]
                return ({'status': True, 'message': 'Quantity removed', 'cart': carts,
                         'lines': _lines_info(cart, UPDATE_LINE_KEYS)})

            if not data.get('cart_id'):
                return ({'status': False, 'message': 'Please pass cartID for the updation'})
            rec = carts_id
            if not rec:
                any_cart = PosOrder._get_app_cart(customer_id, guest=guest)
                return ({'status': False, 'message': 'Please pass Correct cartID for the updation',
                         'cart_id': any_cart.id if any_cart else 0, 'id_code': 404})
            products_qty = _products_qty(data.get('products_info')) or []
            existing_products = rec.lines.mapped('product_id')
            rec._app_add_products([(p, q) for p, q in products_qty if p not in existing_products])
            recs = [_cart_dict(rec, ('order_line', 'amount_total'))]
            return ({'status': True, 'message': 'Cart Updated Successfully', 'cart': recs,
                     'lines': _lines_info(rec, UPDATE_LINE_KEYS)})
        except Exception as e:
            _logger.exception("cart/update failed: %s", e)
            return ({'status': False, 'message': 'Please Pass Correct Info', 'id_code': 404, 'error': str(e),
                     'cart_id': carts_id.id})

    @http.route('/api/v1/cart/delete', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_delete_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        customer_id, guest, error = _resolve_customer(kwargs)
        if error:
            return error
        if not customer_id:
            return ({'status': False, 'message': 'You are not a Valid user'})
        cart = request.env['pos.order'].sudo()._get_app_cart(
            customer_id, cart_id=_to_int(kwargs.get('cart_id')), guest=guest)
        if cart:
            cart.mark_deleted()
            return ({'status': True, 'message': 'Cart Deleted Successfully'})
        return ({'status': False, 'message': 'Invalid Cart ID or Cart Not Found'})

    # Cart list is starting from here
    @http.route('/api/v1/cart/list/summary', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_list_summary_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        if not kwargs.get('uid'):
            return ({'status': False, 'message': 'Please Pass Correct Info'})
        customer_id, guest, error = _resolve_customer(kwargs)
        if error:
            return error
        domain = [('partner_id', '=', customer_id or 0), ('is_app_order', '=', True),
                  ('cart_chekouted', '=', False), ('state', '=', 'draft')]
        if guest:
            domain.append(('guest_user_id', '=', guest.id))
        orders = request.env['pos.order'].sudo().search(domain)
        carts = [{'id': o.id, 'cart_name': o._app_get_reference(), 'amount_total': o.amount_total} for o in orders]
        return (carts if carts else {'status': False, 'message': 'Sorry Your Cart List Is Empty'})

    @http.route('/api/v1/cart/list/view', type="jsonrpc", methods=['POST'], auth='public', csrf=False, cors='*')
    def cart_list_view_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        if not kwargs.get('uid'):
            return json.dumps({'status': False, 'message': 'Please Pass Correct Info'})
        customer_id, guest, error = _resolve_customer(kwargs)
        if error:
            return error
        domain = [('id', '=', _to_int(kwargs.get('list_id'))), ('partner_id', '=', customer_id or 0),
                  ('is_app_order', '=', True)]
        if guest:
            domain.append(('guest_user_id', '=', guest.id))
        cart = request.env['pos.order'].sudo().search(domain, limit=1)
        return [{
            'id': line.id,
            'product_id': [line.product_id.id, line.product_id.display_name],
            'product_uom_qty': line.qty,
            'price_unit': line.price_unit,
            'price_subtotal': line.price_subtotal,
        } for line in cart.lines]
