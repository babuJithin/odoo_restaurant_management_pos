from odoo.http import request
import json
from odoo import http
from odoo import models, fields, api, _,SUPERUSER_ID
from datetime import datetime, date, timedelta
from odoo.exceptions import UserError
import itertools
import logging
from bs4 import BeautifulSoup
import re
import random
import os
_logger = logging.getLogger(__name__)


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


class Ecommerce_Api_V1(http.Controller):

    @http.route('/api/v1/payment_providers', methods=['GET'], auth='public', csrf=False)
    def GetPaymentList_v1(self, **kwargs):
        payments = request.env['payment.provider'].sudo().search([],limit=3)
        payment_list = []
        payment_types_list = []
        if payments:
            for p in payments:
                val = {'id': p.id, 'name': p.name,
                       'code': p.code or "", 'maximum_amount': p.maximum_amount,
                       }
                payment_list.append(val)
        payment_types= request.env['payment.type'].sudo().search([])
        if payment_types:
            for pt in payment_types:
                vals = {'id': pt.id, 'name': pt.name,
                       'description': pt.description or "", 'type': pt.type,
                       }
                payment_types_list.append(vals)
        return json.dumps({"status": True, "message": "Available Payment Options",
                               "payment_type": payment_types_list,"payment_providers":payment_list})

    @http.route('/api/v1/country_list', methods=['GET'], auth='public', csrf=False)
    def GetCountryList_v1(self, **kwargs):
        country = request.env['res.country'].sudo().search([])
        country_list = []
        if country:
            for c in country:
                val = {'country_name': c.name, 'country_id': c.id,
                       'currency': c.currency_id.name or "", 'currency_id': c.currency_id.id,
                       }
                country_list.append(val)
            return json.dumps({"status": True, "message": "Available Countries",
                               "data": country_list})
        else:
            return json.dumps({"status": False, "message": "No Countries found "})

    @http.route('/api/v1/states', methods=['POST'], auth='public', csrf=False)
    def GetStateList_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        if kwargs.get('keyword'):
            if kwargs.get('country_id'):
                country = request.env['res.country'].sudo().search([('id', '=', int(kwargs.get('country_id')))])
                if country:
                    states = request.env['res.country.state'].search(
                        [('name', 'ilike', str(kwargs.get('keyword'))), ('country_id', '=', country.id)])
                    if states:
                        pass
                        data = []
                        for state in states:
                            state_data = {
                                'id': state.id,
                                'name': state.name,
                                'country_id': country.id,
                                'country_name': country.name,
                            }
                            data.append(state_data)
                        return json.dumps({'status': True, 'message': "Success", 'data': data})
                    else:
                        return json.dumps({'status': False, 'message': "No States Found"})
                else:
                    return json.dumps({'status': False, 'message': "No Country Found",})
            else:
                return json.dumps({'status': False, 'message': "Invalid Country ID"})

        else:
            if kwargs.get('country_id'):
                country = request.env['res.country'].sudo().search([('id', '=', int(kwargs.get('country_id')))])
                if country:
                    states = request.env['res.country.state'].search([('country_id', '=', country.id)])
                    if states:
                        data = []
                        for state in states:
                            state_data = {
                                'id': state.id,
                                'name': state.name,
                                'country_id': country.id,
                                'country_name': country.name,
                            }
                            data.append(state_data)
                        return json.dumps({'status': True, 'message': "Success", 'data': data})
                    else:
                        return json.dumps({'status': False, 'message': "No States Found"})
                else:
                    return json.dumps({'status': False, 'message': "No Country Found"})
            else:
                return json.dumps({'status': False, 'message': "Invalid Country ID", })

    @http.route('/api/v1/view_shipping_address', methods=['POST'], auth='public', csrf=False)
    def viewShippingAddressListing_v1(self, **kwargs):
        try:
            kwargs = http.request.get_json_data() or kwargs
            if kwargs.get('user_id'):
                guest_user = request.env['guest.session']
                is_guest = kwargs.get('is_guest')
                if is_guest == "true":
                    guest_user = request.env['guest.session'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                    if guest_user:
                        user = request.env['res.users'].sudo().get_res_user_public()
                    else:
                        return json.dumps({'status': False, 'message': 'You are not a Valid user'})
                else:
                    user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                if user:
                    val = []
                    if user.partner_id.child_ids:
                        for i in user.partner_id.child_ids:
                            if i.type == 'delivery' and i.guest_user_id == int(kwargs.get('user_id')):
                                val.append({'address_id': i.id,
                                            'name': i.name or '',
                                            'street': i.street or '',
                                            'street1': i.street2 or '',
                                            'email': i.email or '',
                                            'phone': i.phone or '',
                                            'city': i.city or '',
                                            'country_name':i.country_id.name if i.country_id else "",
                                            'country_id': i.country_id.id if i.country_id else 0,
                                            'state_id':i.state_id.id if i.state_id else 0,
                                            'state_name':i.state_id.name if i.state_id else '',
                                            'company_name':i.company_name_ecom if i.company_name_ecom else "",
                                            'zip': i.zip or '',
                                            "vat": i.gst_vat or '',
                                            'type':i.type or '',
                                            })
                            elif i.type == 'invoice'  and  i.guest_user_id == int(kwargs.get('user_id')):
                                val.append({'address_id': i.id,
                                            'name': i.name or '',
                                            'street': i.street or '',
                                            'street1': i.street2 or '',
                                            'email': i.email or '',
                                            'phone': i.phone or '',
                                            'city': i.city or '',
                                            'country_name': i.country_id.name if i.country_id else "",
                                            'country_id': i.country_id.id if i.country_id else 0,
                                            'state_id': i.state_id.id if i.state_id else 0,
                                            'state_name': i.state_id.name if i.state_id else '',
                                            'company_name': i.company_name_ecom if i.company_name_ecom else "",
                                            'zip': i.zip or '',
                                            "vat": i.gst_vat or '',
                                            'type': i.type or ''

                                            })
                        if val:
                            return json.dumps({'status': True, 'message': 'Your Shipping address',
                             'data': val})
                        else:
                            return json.dumps({'status': False, 'message': 'Your Shipping address',
                                 'data': val})
                    else:
                        return json.dumps({'status': False, 'message': "No shipping address found",
                                           })
                else:
                    return json.dumps(
                        {'status': False, 'message': 'User not found',
                         })
            else:
                return json.dumps(
                    {'status': False, 'message': 'Please Enter user_id'})
        except Exception as e:
            return json.dumps(
                {'status': False, 'message': 'Please try Again later', 'message_arabic': 'اعد المحاولة لاحقا',
                 'error': str(e)})



    @http.route('/api/v1/insert_shipping_addr',type="json" ,methods=['POST'], auth='public', csrf=False)
    def insertShippingAddress_web_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        if kwargs.get('user_id'):
            guest_user = request.env['guest.session']
            is_guest = kwargs.get('is_guest')
            if is_guest == "true":
                guest_user = request.env['guest.session'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                if guest_user:
                    user = request.env['res.users'].sudo().get_res_user_public()
                else:
                    return json.dumps({'status': False, 'message': 'You are not a Valid user'})
            else:
                user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
            if user:
                country = False
                if kwargs.get("country_id"):
                    country = request.env['res.country'].sudo().search([('id','=',int(kwargs.get("country_id")))],limit=1)
                    if not country:
                        return ({'status': False, 'message': 'Invalid Country ID'})
                print(kwargs.get('company_name'),"$$$$$$$$$$$$$$$$$$444")
                address = request.env['res.partner'].sudo().create(
                    {
                     'guest_user_id':int(kwargs.get('user_id')),
                     'type': kwargs.get('type') or '',
                     'name': kwargs.get('name') or '',
                     'phone': kwargs.get('phone'),
                     'email': kwargs.get('email'),
                     "gst_vat":kwargs.get('vat'),
                     'street': kwargs.get('street'),
                     'street2': kwargs.get('street1'),
                     'country_id':country.id if country else False,
                     'state_id':kwargs.get('state_id'),
                     'company_name_ecom': kwargs.get('company_name'),
                     'city': kwargs.get('city'),
                     'zip': kwargs.get('zip')})


                user.partner_id.sudo().write({'child_ids': [(4, address.id)]})
                return {'status': True, 'message': 'Shipping address is created sucessfully',
                                   'data': {
                                       'type': address.type,
                                       'name': address.name or "",
                                       'phone': address.phone or "",
                                       'email': address.email or "",
                                       'vat':address.gst_vat or "",
                                       'street': address.street or "",
                                       'street1': address.street2 or "",
                                       'city': address.city or "",
                                       'country_name': address.country_id.name if address.country_id else "",
                                       'country_id': address.country_id.id if address.country_id else 0,
                                       'state_id': address.state_id.id if address.state_id else 0,
                                       'state_name': address.state_id.name if address.state_id else '',
                                       'company_name': address.company_name_ecom,
                                       'zip': address.zip or "",
                                       'address_id': address.id}}
            else:
                return {'status': False, 'message': 'User not found',
                                   }
        else:
            return {'status': False, 'message': 'Please Try again', }



            

    @http.route('/api/v1/update_delivery_addr', methods=['POST'], auth='public', csrf=False)
    def updateShippingAddress_web_v2(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        aid = kwargs.get('aid')
        user_id = kwargs.get('user_id')
        if user_id:
            is_guest = kwargs.get('is_guest')
            if is_guest == "true":
                guest_user = request.env['guest.session'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                if guest_user:
                    user = request.env['res.users'].sudo().get_res_user_public()
                else:
                    return json.dumps({'status': False, 'message': 'You are not a Valid user'})
            else:
                user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
            if not user:
                return json.dumps({'status': False, 'message': 'User not found',
                                   })
            for i in user.partner_id.child_ids:
                if int(i.id) == int(aid):
                    if kwargs.get('name') != None:
                        i.name = kwargs.get('name')
                    if kwargs.get('phone') != None:
                        i.phone = kwargs.get('phone')
                    if kwargs.get('email') != None:
                        i.email = kwargs.get('email')
                    if kwargs.get('street') != None:
                        i.street = kwargs.get('street')
                    if kwargs.get('street1') != None:
                        i.street2 = kwargs.get('street1')
                    if kwargs.get('city') != None:
                        i.city = kwargs.get('city')
                    if kwargs.get('zip') != None:
                        i.zip = kwargs.get('zip')
                    if kwargs.get('vat') != None:
                        i.gst_vat = kwargs.get('vat')
                    if kwargs.get('country_id') != None:
                        i.country_id = kwargs.get('country_id')
                    if kwargs.get('state_id') != None:
                        i.country_id = kwargs.get('country_id')
                    if kwargs.get('company_name') != None:
                        i.company_name_ecom = kwargs.get('company_name')
                    if kwargs.get('type') != None:
                        i.type = kwargs.get('type')
            return json.dumps({'status': True, 'message': 'Shipping address is updated sucessfully',
                               })

        else:
            return json.dumps({'status': False, 'message': 'Please Try again', })

    @http.route('/api/v1/deleteDeliveryAddress', methods=['POST'], auth='public', csrf=False)
    def deleteShippingAddress_web_v2(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        aid = kwargs.get('aid')
        user_id = kwargs.get('user_id')
        if user_id:
            is_guest = kwargs.get('is_guest')
            if is_guest == "true":
                guest_user = request.env['guest.session'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                if guest_user:
                    user = request.env['res.users'].sudo().get_res_user_public()
                else:
                    return json.dumps({'status': False, 'message': 'You are not a Valid user'})
            else:
                user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
            try:
                for i in user.partner_id.child_ids:
                    if int(i.id) == int(aid):
                        i.active = False
                        print("dsds")
                return json.dumps({'status': True, 'message': 'Shipping address is Deleted sucessfully',
                                   })
            except Exception as e:
                return json.dumps({'status': False,
                                   'message': 'Address already used in sale order, so unable to delete delivery address'})
        else:
            return json.dumps({'status': False, 'message': 'Please Try again'})

    @http.route('/api/v1/shipping_charge', methods=['POST'], auth='public', csrf=False)
    def get_shipping_charge(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        user_id = kwargs.get('user_id')
        if kwargs.get('address_id') and kwargs.get('user_id') and kwargs.get('cart_id'):
            if user_id:
                is_guest = kwargs.get('is_guest')
                if is_guest == "true":
                    guest_user = request.env['guest.session'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
                    if guest_user:
                        user = request.env['res.users'].sudo().get_res_user_public()
                    else:
                        return json.dumps({'status': False, 'message': 'You are not a Valid user'})
                else:
                    user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
            cart_id = kwargs.get('cart_id')
            shipping_method = request.env['delivery.carrier'].sudo().search([('id', '=', 1)], limit=1)
            if shipping_method:
                cart = request.env['pos.order'].sudo().search([('id', '=', _to_int(cart_id))])
                if cart and cart.lines:
                    if not cart.partner_id:
                        return json.dumps(
                            {'status': False, 'message': "No Customer Selected in Cart"})
                else:
                    return json.dumps(
                        {'status': False, 'message': "Invalid Cart ID"})
                shipping_data = {
                    'id': shipping_method.id,
                    'name': shipping_method.name,
                    'charge': 0.0,
                    'tax': 0.0,
                }
                return json.dumps(
                    {'status': True, 'message': "Success", 'data': shipping_data})
            else:
                return json.dumps({'status': False, 'message': "No Shipping Method Found"})
        else:
            return json.dumps(
                {'status': False, 'message': "Invalid Adress ID or User ID or Cart ID"})

    @http.route('/api/v1/checkOut', methods=['POST'], type="json", auth='public', csrf=False)
    def checkout_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        guest_user = request.env['guest.session']
        user = request.env['res.users']
        user_id = kwargs.get('user_id')
        if user_id:
            if kwargs.get('is_guest') == "true":
                guest_user = request.env['guest.session'].sudo().search([('id', '=', _to_int(user_id))])
                if guest_user:
                    user = request.env['res.users'].sudo().get_res_user_public()
                else:
                    return {'status': False, 'message': 'You are not a Valid user'}
            else:
                user = request.env['res.users'].sudo().search([('id', '=', _to_int(user_id))])
        if not user:
            return {'status': False, 'message': 'You are not a Valid User'}

        PosOrder = request.env['pos.order'].sudo()
        cart_id = PosOrder._get_app_cart(user.partner_id, cart_id=_to_int(kwargs.get('cart_id')),
                                         guest=guest_user or None)
        if not cart_id.partner_id:
            return {'status': False, 'message': 'You are not a Valid User'}
        if not kwargs.get('address_id'):
            return {'status': False, 'message': 'Invalid Shipping Address For Home Delivery'}
        address = request.env['res.partner'].sudo().search([('id', '=', _to_int(kwargs.get('address_id')))])
        if not address:
            return {'status': False, 'message': ' Shipping Address Not Found'}
        if not cart_id.lines:
            return {'status': False, 'message': 'No Cart Lines Found'}

        Carrier = request.env['delivery.carrier'].sudo()
        delivery = Carrier
        if kwargs.get('delivery_id'):
            delivery = Carrier.search([('active', '=', True), ('id', '=', _to_int(kwargs.get('delivery_id')))], limit=1)
        if not delivery:
            # former behaviour: _check_carrier_quotation(1)
            delivery = Carrier.search([('id', '=', 1)], limit=1)

        payment_type_rec = request.env['payment.type']
        if kwargs.get('payment_id'):
            payment_type_rec = request.env['payment.type'].sudo().search([('id', '=', _to_int(kwargs.get('payment_id')))])

        val = {
            'cart_chekouted': True,
            'partner_shipping_id': address.id,
            'marketplace_state': 'new',
        }
        if kwargs.get('OrderDate'):
            val['date_order'] = kwargs.get('OrderDate')
        if kwargs.get('date'):
            val['delivery_date'] = kwargs.get('date')
        if kwargs.get('order_platform'):
            val['order_platform'] = kwargs.get('order_platform')
        if kwargs.get('order_note'):
            val['general_customer_note'] = kwargs.get('order_note')
        if kwargs.get('payment_type'):
            val['payment_type'] = kwargs.get('payment_type')
        if kwargs.get('transaction_id'):
            val['transaction_id'] = kwargs.get('transaction_id')
        if payment_type_rec:
            val['payment_method'] = payment_type_rec.id
        if guest_user:
            val['guest_checkout'] = True
            val['guest_user_id'] = guest_user.id
            # guest orders stay on the public partner; contact details go to the native fields
            val['email'] = address.email or False
            val['mobile'] = address.phone or False

        cart_id.write(val)
        if delivery:
            cart_id._app_add_delivery_line(delivery)

        # card / online orders are paid now, COD orders stay unpaid until delivery
        payment_kind = cart_id.payment_type or (
            {'card': 'card', 'online': 'online', 'cash': 'COD'}.get(payment_type_rec.type) if payment_type_rec else False)
        pay_now = payment_kind in ('card', 'online')
        if payment_kind and not cart_id.payment_type:
            cart_id.payment_type = payment_kind

        candidate_method = payment_type_rec.pos_payment_method_id if pay_now and payment_type_rec else None
        cart_id._app_move_to_target_session(candidate_method)
        cart_id.name = cart_id._compute_order_name()

        if pay_now:
            payment_method = cart_id._app_payment_method(payment_type_rec)
            try:
                with request.env.cr.savepoint():
                    if not payment_method:
                        raise UserError(_("No card/online payment method in point of sale %s", cart_id.config_id.name))
                    cart_id._app_register_payment(payment_method, cart_id.transaction_id)
            except Exception as e:
                request.env.invalidate_all()
                _logger.exception("Payment registration failed for app order %s", cart_id.id)
                cart_id.message_post(body=_("Automatic payment registration failed, please validate the payment "
                                            "manually (transaction %(tx)s): %(err)s",
                                            tx=cart_id.transaction_id or '-', err=str(e)))

        order_info = []
        for i in cart_id.lines:
            rec = {
                "product_id": i.product_id.id,
                "product_name": i.product_id.name,
                "category_name": i.product_id.categ_id.name,
                "internal_reference": i.product_id.default_code or "",
                "order_qty": i.qty or 0.0,
                "unit_price": i.price_unit or 0.0,
                "tax": 0.0,
                "subtotal_without_tax": i.price_subtotal or 0.0,
                "subtotal": i.price_subtotal or 0.0
            }
            order_info.append(rec)

        amount_without_discount = cart_id._app_amount_undiscounted()
        try:
            with request.env.cr.savepoint():
                cart_id._app_send_confirmation_mail()
        except Exception:
            _logger.exception("Order confirmation mail failed for app order %s", cart_id.id)
        try:
            with request.env.cr.savepoint():
                cart_id._app_notify_pos()
        except Exception:
            _logger.exception("POS notification failed for app order %s", cart_id.id)

        final_message = 'Order Created successfully'
        return {
            'status': True,
            'message': str(final_message),
            'sale_order_no': str(cart_id._app_get_reference()),
            'order_id': cart_id.id,
            "items": order_info,
            'total_amount_without_discount': amount_without_discount,
            'tax': 0.0,
            'total_amount_without_tax': cart_id.amount_total,
            'total_amount': cart_id.amount_total}

    @staticmethod
    def _history_line(product, qty, uom, price_unit, subtotal, status):
        return {'productName': product.name or "", 'image': "http://" + str(
            http.request.httprequest.host) + "/website/image/product.product/{}/image_1920".format(
            product.id) if product.image_1920 else "",
                'status': status or "",
                'quantity': qty or 0, 'product_uom': uom.name or "",
                'product_uom_id': uom.id or 0, 'price': price_unit or 0,
                'totalPrice': subtotal or 0,
                "is_delivery_charge": True if product.default_code == 'Delivery_007' else False}

    @staticmethod
    def _pos_history_status(order):
        if order.state == 'cancel' or order.marketplace_state == 'cancel':
            return "Cancelled"
        if order.marketplace_state in ('shipped', 'delivered'):
            return "Shipped"
        return "Processing"

    @staticmethod
    def _sale_history_status(order):
        return {'sent': "Processing", 'sale': "Shipped", 'cancel': "Cancelled"}.get(order.state, "Processing")

    @http.route('/api/v1/orderHistory', methods=['POST'], type='json', auth='public', csrf=False)
    def sale_order_history_web_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        uid = _to_int(kwargs.get('user_id'))
        user = request.env['res.users'].sudo().search([('id', '=', uid)]) if uid else request.env['res.users']
        if not user:
            return {'message': "You are not a Valid User", 'status': False}
        partner_id = user.partner_id.id
        entries = []  # (sort datetime, vals)

        pos_orders = request.env['pos.order'].sudo().search(
            [('cart_chekouted', '=', True), ('partner_id', '=', partner_id)])
        for order in pos_orders:
            status = self._pos_history_status(order)
            vals = {'sale_order_id': order.id or 0,
                    'orderNumber': order._app_get_reference() or "",
                    'total': order.amount_total or 0, 'order_line': [],
                    'customer': order.partner_id.name or ""}
            for i in order.lines:
                vals['order_line'].append(self._history_line(
                    i.product_id, i.qty, i.product_uom_id, i.price_unit, i.price_subtotal, status))
            if order.delivery_date:
                vals['orderDate'] = order.delivery_date.strftime('%Y-%m-%d')
            else:
                vals['orderDate'] = order.date_order.strftime('%Y-%m-%d')
            entries.append((order.date_order, vals))

        # transition: historic app orders stored as sale.order
        sale_orders = request.env['sale.order'].sudo().search(
            [('cart_chekouted', '=', True), ('partner_id', '=', partner_id)])
        for order in sale_orders:
            status = self._sale_history_status(order)
            vals = {'sale_order_id': order.id or 0,
                    'orderNumber': order.name or "",
                    'total': order.amount_total or 0, 'order_line': [],
                    'customer': order.partner_id.name or ""}
            for i in order.order_line:
                vals['order_line'].append(self._history_line(
                    i.product_id, i.product_uom_qty, i.product_uom_id, i.price_unit, i.price_subtotal, status))
            if order.commitment_date:
                vals['orderDate'] = order.commitment_date.strftime('%Y-%m-%d')
            else:
                vals['orderDate'] = order.date_order.strftime('%Y-%m-%d')
            entries.append((order.date_order, vals))

        if not entries:
            return {'message': "Sorry no orders found for this user", 'status': False}
        entries.sort(key=lambda e: e[0] or datetime.min, reverse=True)
        order_details = [vals for _date, vals in entries]
        return {'message': 'Order history', 'status': True, 'data': {'orderDetails': order_details}}
