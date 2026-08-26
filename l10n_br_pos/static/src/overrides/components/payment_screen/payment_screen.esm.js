import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {
    /**
     * Liga/desliga a transmissão do documento fiscal desta venda.
     *
     * Emitir exige faturar: sem fatura não há documento fiscal para
     * transmitir, então marcar a emissão marca a fatura junto.
     */
    toggleL10nBrEmitDocument() {
        const emit = !this.currentOrder.l10n_br_emit_document;
        this.currentOrder.update({l10n_br_emit_document: emit});
        if (emit && !this.currentOrder.is_to_invoice()) {
            this.currentOrder.set_to_invoice(true);
        }
    },
});
