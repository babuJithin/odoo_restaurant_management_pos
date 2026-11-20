# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import itertools
from datetime import datetime, date, timedelta
import time
import random
import logging
_logger = logging.getLogger(__name__)
import uuid
import re


class CustomGuestSession(models.Model):
    _name = 'guest.session'
    _description = 'Guest Session'

    session_id = fields.Char(string="Session ID")


class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_name_ecom = fields.Char(string="Company Name")
    gst_vat = fields.Char(string="Gst vat")
    guest_user_id = fields.Integer(string="Guest USER id")


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_res_user_public(self):
        public_user = self.env.ref('base.public_user')
        if public_user:
            return public_user
        else:
            return False

    def create_temp_res_user(self):
        """Create a throw-away portal user for guest flows.

        The former implementation wrote the database-dependent pseudo field
        ``sel_groups_1_9_10`` (its name depends on the group ids of the database it was
        generated on) and the non-existent fields ``is_guest_user`` / ``login_mobile``.
        The group is now set explicitly through ``group_ids`` and optional fields are only
        written when they exist on res.users.
        """
        chrs = 'ABCDEFHIJITYDSNCJSUJDBSIBDSJSNOAHaskjdssoibdiusbabcdef0123456789'
        random_key = ''.join(random.choices(chrs, k=15))
        vals = {
            'login': random_key + "@gmail.com",
            'name': random_key,
        }
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if portal_group:
            vals['group_ids'] = [(6, 0, [portal_group.id])]
        users_fields = self.env['res.users']._fields
        if 'is_guest_user' in users_fields:
            vals['is_guest_user'] = True
        if 'login_mobile' in users_fields:
            vals['login_mobile'] = random_key
        return self.env['res.users'].sudo().with_context(no_reset_password=True).create(vals)
