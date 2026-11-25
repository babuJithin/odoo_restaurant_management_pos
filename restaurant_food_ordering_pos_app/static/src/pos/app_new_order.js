import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setup() {
        await super.setup(...arguments);
        this.data.connectWebSocket("APP_NEW_ORDER", (payload) => this.onAppNewOrder(payload));
    },

    /** Mobile app orders waiting to be accepted (badge on the Orders button). */
    get appWaitingOrderCount() {
        return this.models["pos.order"].filter(
            (o) =>
                o.is_app_order &&
                o.cart_chekouted &&
                o.state === "draft" &&
                (o.marketplace_state || "new") === "new"
        ).length;
    },

    async onAppNewOrder(payload) {
        if (payload.session_id && payload.session_id !== odoo.pos_session_id) {
            return;
        }
        try {
            this.sound?.play("order-receive-tone");
        } catch {
            // browsers may block audio until the cashier interacted with the page
        }
        try {
            // load it now, without waiting for the next synchronisation
            await this.data.loadServerOrders([["id", "=", payload.order_id]]);
        } catch {
            // the regular synchronisation will bring it in
        }
        const amount = this.env.utils.formatCurrency(payload.amount || 0);
        this.notification.add(
            _t("%(name)s · %(customer)s · %(amount)s", {
                name: payload.name,
                customer: payload.customer || _t("Guest"),
                amount,
            }),
            {
                title: _t("New mobile app order"),
                type: "warning",
                sticky: true,
                buttons: [
                    {
                        name: _t("Open"),
                        primary: true,
                        onClick: () => this.navigate("TicketScreen"),
                    },
                ],
            }
        );
    },
});
