from odoo.http import request
import json
from odoo import http
from .Api_Exposing_product_v1 import _base_url
from odoo import models, fields, api, _,SUPERUSER_ID
from datetime import datetime, date, timedelta
import itertools
import logging
import re
import random
import os
_logger = logging.getLogger(__name__)
from werkzeug.urls import url_join
from .Api_Exposing_product_v1 import _product_type_prices


def _wishlist_offer_price(template, base_price):
    """Same offer-price logic as the product listing APIs; returns 0 if no active offer."""
    try:
        pricelist = request.env['product.pricelist.item'].sudo().search(
            [('product_tmpl_id', '=', int(template.id))])
        offers = [base_price - (base_price * item.percent_price / 100) if item.percent_price > 0 else (
            base_price - item.discount_amount if item.discount_amount > 0 else item.fixed_price)
                  for item in pricelist if
                  (not item.date_end and item.pricelist_id.selectable) or (
                          item.date_end and item.date_end >= datetime.now() and item.pricelist_id.selectable)]
        return offers[0]
    except Exception:
        return 0


class Ecommerce_Api_Wishlist_V1(http.Controller):


    @http.route('/api/v1/addWishlist', methods=['POST'] , type='jsonrpc', auth='public', csrf=False)
    def add_product_wishlist_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
        product = request.env['product.product'].sudo().search(
            [('product_tmpl_id', '=', int(kwargs.get('product_id')))])

        if user and product:
            if request.env['product.wishlist'].sudo().search([('product_id', '=', product[0].id),
                                                              ('partner_id', '=', int(user.partner_id.id))]).exists():
                return {'status': 'False', 'message': 'Your Product is already added to wishlist'}
            else:
                wishlist = request.env['product.wishlist'].sudo().create(
                    {'product_id': product[0].id, 'partner_id': user.partner_id.id, 'website_id': 1})
                if wishlist:
                    return {'status': True, 'message': 'successfully product added to wishlist'}
                else:
                    return {'status': False, 'message': 'Please try again later'}
        else:
            return {'status': False, 'message': 'You are not a Valid User / Invalid Product'}

    @http.route('/api/v1/removefromwishlist', methods=['POST'],type='jsonrpc', auth='public', csrf=False)
    def remove_product_wishlist_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs

        user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
        product = request.env['product.product'].sudo().search(
            [('product_tmpl_id', '=', int(kwargs.get('product_id')))])
        if user and product:
            wishlist = request.env['product.wishlist'].sudo().search([('product_id', '=', product[0].id), (
                'partner_id', '=', int(user.partner_id.id))])
            if wishlist:
                wishlist.sudo().unlink()
                return {'status': True, 'message': 'successfully product removed from wishlist'}

            else:
                return {'status': False, 'message': 'Please try again later'}
        else:
            return {'status': False, 'message': 'You are not a Valid User'}

    @http.route('/api/v1/userWishlist', methods=['POST'], type='jsonrpc', auth='public', csrf=False)
    def all_wishlis_web_v1(self, **kwargs):
        kwargs = http.request.get_json_data() or kwargs
        user = request.env['res.users'].sudo().search([('id', '=', int(kwargs.get('user_id')))])
        all_wishlist = []
        if user:
            wishlist = request.env['product.wishlist'].sudo().search([('partner_id', '=', int(user.partner_id.id))])
            if wishlist:
                for i in wishlist:
                    vals = {
                        "product_id": i.product_id.product_tmpl_id.id,
                        "main_category_id":
                            [categ_id.id for categ_id in i.product_id.product_tmpl_id.pos_categ_ids if
                             categ_id.parent_id.id == False][0] if [categ_id.id for categ_id in
                                                                    i.product_id.product_tmpl_id.pos_categ_ids if
                                                                    categ_id.parent_id.id == False] else '',
                        "is_wishlist": True,
                        "product": i.product_id.product_tmpl_id.name or "",
                        "product_url": str(i.product_id.product_tmpl_id.website_url),
                        "product_code": i.product_id.product_tmpl_id.default_code or "",
                        "quantity": i.product_id.product_tmpl_id.qty_available or 0,
                        "product_uom": i.product_id.product_tmpl_id.uom_id.name or "",
                        "product_uom_id": i.product_id.product_tmpl_id.uom_id.id or 0,
                        "price": round(_wishlist_offer_price(i.product_id.product_tmpl_id, i.product_id.product_tmpl_id.list_price), 2) or round(i.product_id.product_tmpl_id.list_price, 2) or 0,
                        "org_price": round(i.product_id.product_tmpl_id.list_price, 2),
                        "status": "1",
                        "available": False,
                        "product_image": _base_url() + "/website/image/product.template/{}/image_1920".format(
                            i.product_id.product_tmpl_id.id) if i.product_id.product_tmpl_id.image_1920 else "False",

                        "product_image_512": _base_url() + "/website/image/product.template/{}/image_512".format(
                            i.product_id.product_tmpl_id.id) if i.product_id.product_tmpl_id.image_512 else "False",

                        "product_type_prices": _product_type_prices(i.product_id.product_tmpl_id),

                        "product_type": []}

                    for variant in request.env['product.product'].sudo().search(
                            [('product_tmpl_id', '=', i.product_id.product_tmpl_id.id)]):
                        vals1 = {
                            "product_type_id": variant.id or 0,
                            "price": round(_wishlist_offer_price(i.product_id.product_tmpl_id, variant.list_price), 2) or round(i.product_id.product_tmpl_id.list_price, 2) or 0,
                            "org_price": round(i.product_id.product_tmpl_id.list_price, 2),
                            "quantity": variant.qty_available or 0,
                            "product_uom": variant.uom_id.name or "",
                            "product_uom_id": variant.uom_id.id or 0,
                            "product_id": i.product_id.product_tmpl_id.id or 0,
                            "created_at_date": variant.create_date.strftime('%Y-%m-%d'),
                            "status": "1",
                            "product_type_name": ','.join(
                                [str(v.display_name) for v in variant.product_template_attribute_value_ids]),
                        }

                        vals['product_type'].append(vals1)
                    if i.product_id.product_tmpl_id.active == True and i.product_id.product_tmpl_id.available_in_pos == True:
                        vals['available'] = True
                    all_wishlist.append(vals)

                return {'status': True, 'message': 'Your wishlist is', 'data': {'products': all_wishlist}}

            else:
                return {'status': False, 'message': 'Your wishlist is empty'}
        else:
            return {'status': False, 'message': 'You are not a Valid User'}






















