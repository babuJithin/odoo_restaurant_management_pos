# Changelog

## 19.0.1.0.1

### Module rename
- Technical name `restaurant_app_builder` → `restaurant_food_ordering_pos_app`.
  Display name: "Android Mobile App for Restaurant Food Ordering POS Application".
- All `restaurant_app_builder.*` references (XML ids, menus, `env.ref`, web_icon) updated.
- `migrations/19.0.1.0.1/pre-migrate.py` renames `ir_module_module`, `ir_model_data`,
  `ir_module_module_dependency` and `base.module_<name>` rows.
  **Existing databases:** Odoo only runs migrations for a module row that already has the new
  name. Run the same SQL once before the upgrade (see the docstring), then
  `-u restaurant_food_ordering_pos_app`.

### Storage: sale.order → pos.order (API contract unchanged)
App carts are draft `pos.order` records (`is_app_order = True`) in a dedicated **Mobile App**
point of sale. It is created at install, or on the first API call if the company has no chart of
accounts yet. Its session opens automatically. At checkout an order moves to the restaurant
session when *Settings › Point of Sale › Mobile App Orders › Send App Orders To* is set and that
session is open. Otherwise it stays in the Mobile App point of sale.

| Endpoint | Internal change |
|---|---|
| `/api/v1/cart/create` | `pos.order._get_app_cart()` finds the cart, or `_app_create_cart()` creates it with `session_id`; lines come from `_prepare_pos_line_vals()` (pricelist price, company taxes, fiscal position); then `_app_recompute()` |
| `/api/v1/cart/update` | `qty` replaces `product_uom_qty`; qty 0 deletes the line; only lines of the caller's own cart can be changed; `_app_recompute()` runs after every change; `price` = line `price_unit` |
| `/api/v1/cart/summary`, `/cart/view` | `lines` replaces `order_line`; `amount_without_discount` = Σ price_unit × qty; `price` = line `price_unit` |
| `/api/v1/cart/delete` | `pos.order.mark_deleted()` (draft unlink: cancel then delete) |
| `/api/v1/cart/list/summary` | Fixed: searched fields that don't exist (`partner_id_id`, `cart_name`); now returns `[{id, cart_name, amount_total}]` |
| `/api/v1/cart/list/view` | Fixed: removed `request.jsonrequest`; runs with sudo; limited to the caller's own app orders; same row keys |
| `/api/v1/shipping_charge` | Reads the cart from `pos.order` (response unchanged, charge still 0.0) |
| `/api/v1/checkOut` | No `state='sent'` (`cart_chekouted=True` is the flag); `partner_shipping_id`, `general_customer_note`, platform, payment type; carrier product added as a POS line at the carrier price (`_app_add_delivery_line`); card/online → `pos.payment` + `action_pos_order_paid()` + real-time picking; COD left unpaid; guest email/mobile stored on the order; confirmation via `mail_template_app_pos_order`; open POS screens notified (`notify_synchronisation` + `ORDER_STATE_CHANGED` + `_send_order()` kitchen hook). Fixed: crash when `user_id` is missing |
| `/api/v1/orderHistory` | Reads `pos.order` **and** legacy `sale.order`, sorted by date (newest first); `status` always set (Processing / Shipped / Cancelled); `delivery_date` replaces `commitment_date`; legacy lines use `product_uom_id` (the Odoo 19 field name) |
| Product APIs + `/api/v1/mobileHome` | Added `available_in_pos = True` to the product domains; `detailed_type` (removed in Odoo 17+) is now filled from `type` |

### Other
- POS UI never loads app carts that aren't checked out (`_load_pos_data_domain`).
- Session closing: app carts, and unpaid orders in the Mobile App point of sale, no longer block
  closing. They move to the next Mobile App session (or are cancelled after N days, a new
  setting). Unpaid COD orders in the restaurant session still block closing until they are paid.
- `payment.type.pos_payment_method_id`: the POS payment method used for card/online payments.
- Custom app fields are declared once on `pos.order`. Legacy copies are consolidated on
  `sale.order` (in `models/sale_order.py`).
- `create_temp_res_user()` uses `group_ids` (portal) instead of `sel_groups_1_9_10`.
- ACLs added for custom models that had none (home.delivery.type, zone.location, guest.session,
  user.otp.registry, product.brand).

## Regression test checklist
- [ ] cart create / update / delete as a user and as a guest: JSON keys identical to before
- [ ] Two guests get separate carts
- [ ] Cart totals match the same order keyed in the POS UI (pricelist, taxes, fiscal position)
- [ ] Cart creation when no Mobile App session is open: session auto-opens (`opened`)
- [ ] Checkout card: order `paid`, `pos.payment` with transaction id, picking `done`, stock reduced
- [ ] Checkout online: same as card, using the payment type's POS method
- [ ] Checkout COD: order `draft` and checked out, visible in the POS UI, settled with the Payment button / POS UI
- [ ] Delivery line (`Delivery_007`) added at the carrier price; `is_delivery_charge` true in history
- [ ] Confirmation e-mail queued for user and guest (guest e-mail/mobile on the order)
- [ ] Closing the Mobile App session with abandoned carts: closes, carts move to the new session
- [ ] Closing the restaurant session with unpaid COD: blocked until paid or cancelled
- [ ] orderHistory shows old sale orders and new POS orders, newest first
- [ ] Checked-out order appears on the open restaurant POS / kitchen display without a reload
- [ ] Products with `available_in_pos = False` are hidden from the product, search and home APIs
- [ ] Upgrading a DB that has the old module name keeps all data (run the rename SQL first)
