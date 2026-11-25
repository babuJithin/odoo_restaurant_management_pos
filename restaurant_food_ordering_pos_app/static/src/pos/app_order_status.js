import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";

// marketplace_state on pos.order -> label / badge colour / next step shown to the cashier
export const APP_STATUS = {
    new: { label: _t("Waiting"), color: "warning", next: "approved", action: _t("Accept") },
    approved: { label: _t("Accepted"), color: "info", next: "processing", action: _t("Start Preparing") },
    processing: { label: _t("Preparing"), color: "primary", next: "shipped", action: _t("Out for Delivery") },
    shipped: { label: _t("On the way"), color: "dark", next: "delivered", action: _t("Mark Delivered") },
    delivered: { label: _t("Delivered"), color: "success" },
    cancel: { label: _t("Cancelled"), color: "danger" },
};

export function isAppOrder(order) {
    return Boolean(order?.is_app_order && order?.cart_chekouted);
}

export function isOpenAppOrder(order) {
    return isAppOrder(order) && order.state === "draft" && !["delivered", "cancel"].includes(order.marketplace_state);
}

export function appStatus(order) {
    if (!isAppOrder(order)) {
        return null;
    }
    if (order.state === "cancel") {
        return APP_STATUS.cancel;
    }
    if (order.state !== "draft") {
        return APP_STATUS.delivered;
    }
    return APP_STATUS[order.marketplace_state || "new"] || APP_STATUS.new;
}

async function setAppOrderStatus(pos, order, newState) {
    // push local edits (e.g. a changed payment line) before the server acts on the order
    if (order.isDirty?.()) {
        await pos.syncAllOrders({ orders: [order], throw: true });
    }
    await pos.data.callRelated(
        "pos.order",
        "app_pos_set_status",
        [[order.id], newState, pos.config.id],
        { context: { device_identifier: pos.device?.identifier } },
        false
    );
    if (["delivered", "cancel"].includes(newState) && pos.getOrder() === order) {
        const { page, params } = pos.defaultPage;
        pos.navigate(page, params);
    }
}

const appStatusMethods = {
    appStatus(order) {
        return appStatus(order);
    },
    isOpenAppOrder(order) {
        return isOpenAppOrder(order);
    },
    async onClickAppNextStatus(order) {
        const status = appStatus(order);
        if (!status?.next) {
            return;
        }
        await setAppOrderStatus(this.pos, order, status.next);
    },
    onClickAppCancel(order) {
        const paid = order.payment_ids.some((p) => p.payment_status === "done");
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cancel app order"),
            body: paid
                ? _t("This order was already paid in the app. It will be cancelled and the payment must be refunded manually. Continue?")
                : _t("Cancel this mobile app order?"),
            confirmLabel: _t("Cancel Order"),
            confirm: () => setAppOrderStatus(this.pos, order, "cancel"),
            cancel: () => {},
        });
    },
};

patch(ControlButtons.prototype, appStatusMethods);
patch(TicketScreen.prototype, {
    ...appStatusMethods,
    shouldHideDeleteButton(order) {
        // app orders are cancelled with the dedicated button (refund rules)
        return isAppOrder(order) || super.shouldHideDeleteButton(...arguments);
    },
});
