import {PosOrder} from "@point_of_sale/app/models/pos_order";
import {patch} from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * Leva o documento fiscal do cliente ao recibo.
     *
     * O cabeçalho já imprime o CNPJ de quem emite; quem compra fica sem. No
     * balcão brasileiro o cliente pede o documento na nota, e o recibo é o
     * comprovante que ele leva na mão.
     */
    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        const partner = this.get_partner();
        if (partner) {
            result.l10n_br_partner = {
                name: partner.name,
                vat: partner.vat || "",
                vat_label: this.company.country_id?.vat_label || "",
            };
        }
        return result;
    },
});
