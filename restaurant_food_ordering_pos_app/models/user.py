from odoo import api, fields, models, tools, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError, RedirectWarning, UserError
import secrets
import contextlib
from datetime import datetime, timedelta


class UserInherit(models.Model):
    _inherit = 'res.users'

    phone_number = fields.Char(string="Phone")

    def _action_reset_password_ecommerce(self):
        """Send the password reset link to app users.

        Odoo 19 removed the ``expiration`` argument of ``signup_prepare()`` and sends the reset
        mail through the ``auth_signup.reset_password_email`` mail.template, so rely on the
        standard flow (token validity is handled by ``auth_signup.reset_password.validity``).
        """
        return self.sudo().with_context(create_user=False).action_reset_password()


class UserOtpRegistry(models.Model):
    _name = 'user.otp.registry'
    _description = 'User OTP Registry'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email', required=True)
    phone_number = fields.Char(string='Phone Number')
    otp = fields.Char(string='OTP')

    def generate_otp(self):
        """Random 6-digit one-time code (the former TOTP used a hard-coded, public secret, so the
        code was predictable, and recent pyotp versions reject that secret)."""
        return '%06d' % secrets.randbelow(10 ** 6)

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