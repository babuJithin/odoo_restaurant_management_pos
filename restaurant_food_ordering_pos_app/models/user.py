from odoo import api, fields, models, tools, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError, RedirectWarning, UserError
import pyotp
import contextlib
from datetime import datetime, timedelta


class UserInherit(models.Model):
    _inherit = 'res.users'

    phone_number = fields.Char(string="Phone")

    def _action_reset_password_ecommerce(self):

        if self.filtered(lambda user: not user.active):
            raise UserError(_("You cannot perform this action on an archived user."))

        # no time limit for initial invitation, only for reset password
        expiration = datetime.now() + timedelta(days=1)

        self.mapped('partner_id').signup_prepare(signup_type="reset", expiration=expiration)

        # send email to users with their signup url

        email_values = {
            'email_cc': False,
            'auto_delete': True,
            'message_type': 'user_notification',
            'recipient_ids': [],
            'partner_ids': [],
            'scheduled_date': False,
        }

        for user in self:
            if not user.login:
                raise UserError(_("Cannot send email: user %s has no email address.", user.name))
            email_values['email_to'] = user.login
            with contextlib.closing(self.env.cr.savepoint()):
                # NOTE: verify this render call still matches the mail.render.mixin
                # signature on your installed Odoo 19 build before relying on it in
                # production - the internal rendering API has shifted across
                # versions and is not guaranteed stable between 17 and 19.
                body = self.env['mail.render.mixin']._render_template(
                    self.env.ref('auth_signup.reset_password_email'),
                    model='res.users', res_ids=user.ids,
                    engine='qweb_view', options={'post_process': True})[user.id]
                mail = self.env['mail.mail'].sudo().create({
                    'subject': _('Password reset'),
                    'email_from': "abhijith.soman0@gmail.com",
                    'body_html': body,
                    **email_values,
                })
                mail.send()
                _logger.info("Password reset email sent for user <%s> to <%s>", user.name, user.login)


class UserOtpRegistry(models.Model):
    _name = 'user.otp.registry'
    _description = 'User OTP Registry'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True)
    phone_number = fields.Char(string='Phone Number')
    otp = fields.Char(string='OTP')

    def generate_otp(self):
        # NOTE: with multiple records in self, this only ever computes and
        # returns the OTP for the first record (the loop body `return`s on the
        # first iteration). If you intend to generate/store an OTP per record,
        # write it to `rec.otp` inside the loop instead of returning early.
        for rec in self:
            totp = pyotp.TOTP('base32secret3232')
            login_otp = totp.now()
            return login_otp

    def _action_send_signup_otp(self):
        """ send email to users with their registration otp """

        email_values = {
            'email_cc': False,
            'auto_delete': True,
            'message_type': 'user_notification',
            'recipient_ids': [],
            'partner_ids': [],
            'scheduled_date': False,
        }

        for user in self:
            if not user.email:
                raise UserError(_("Cannot send email: user %s has no email address.", user.name))
            email_values['email_to'] = user.email
            body = self.env['mail.render.mixin']._render_template(
                self.env.ref('restaurant_food_ordering_pos_app.otp_signup_email'),
                model='user.otp.registry', res_ids=user.ids,
                engine='qweb_view', options={'post_process': True})[user.id]
            mail = self.env['mail.mail'].sudo().create({
                'subject': _('OTP'),
                'email_from': "abhijith.soman0@gmail.com",
                'body_html': body,
                **email_values,
            })
            mail.send()

            _logger.info("OTP For Registration Sent For User <%s> to <%s>", user.name, user.email)


class HomeDeliveryType(models.Model):
    _name = 'home.delivery.type'
    _description = 'Home Delivery Type'

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    description = fields.Char(string="Description")


class ZoneLocation(models.Model):
    _name = 'zone.location'
    _description = 'Zone Location'

    name = fields.Char(string="Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    description = fields.Char(string="Description")


class PaymentType(models.Model):
    _name = 'payment.type'
    _description = 'Payment Type'

    active = fields.Boolean(string="active", default=True)
    name = fields.Char(string="Name")
    description = fields.Char(string="Description")
    type = fields.Selection([
        ('card', 'Card Payment'),
        ('cash', 'Cash On Delivery'),
        ('online', 'Online Payment')
    ], string="Payment Type")
    pos_payment_method_id = fields.Many2one(
        'pos.payment.method', string="POS Payment Method",
        help="Point of Sale payment method used to register the payment of mobile app orders paid with "
             "this payment type (card / online). Leave empty for Cash On Delivery: the order stays "
             "unpaid and is settled when it is delivered.")