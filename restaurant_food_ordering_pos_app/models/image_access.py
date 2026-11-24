# -*- coding: utf-8 -*-
"""Let the mobile app (public user) load images through /web/image.

/web/image checks read access on the record. website_sale only grants public
read on published + saleable templates, and pos.category / product.brand have
no public ACL at all, so POS-only products and categories fell back to the
placeholder image. Only the image fields are opened up, not the records.
"""
from odoo import models

IMAGE_FIELDS = {'image_1920', 'image_1024', 'image_512', 'image_256', 'image_128'}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in IMAGE_FIELDS and self.sudo().available_in_pos:
            return True
        return super()._can_return_content(field_name, access_token)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in IMAGE_FIELDS and self.sudo().available_in_pos:
            return True
        return super()._can_return_content(field_name, access_token)


class ProductImage(models.Model):
    _inherit = 'product.image'

    def _can_return_content(self, field_name=None, access_token=None):
        rec = self.sudo()
        tmpl = rec.product_tmpl_id or rec.product_variant_id.product_tmpl_id
        if field_name in IMAGE_FIELDS and tmpl.available_in_pos:
            return True
        return super()._can_return_content(field_name, access_token)


class PosCategory(models.Model):
    _inherit = 'pos.category'

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in IMAGE_FIELDS | {'banner'}:
            return True
        return super()._can_return_content(field_name, access_token)

