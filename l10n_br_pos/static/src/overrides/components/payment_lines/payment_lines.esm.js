import {_t} from "@web/core/l10n/translation";
import {CardDataPopup} from "@l10n_br_pos/app/card_data_popup/card_data_popup.esm";
import {makeAwaitable} from "@point_of_sale/app/store/make_awaitable_dialog";
import {patch} from "@web/core/utils/patch";
import {PaymentScreenPaymentLines} from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import {useService} from "@web/core/utils/hooks";
import {usePos} from "@point_of_sale/app/store/pos_hook";

patch(PaymentScreenPaymentLines.prototype, {
    setup() {
        super.setup(...arguments);
        this.l10nBrPos = usePos();
        this.l10nBrDialog = useService("dialog");
    },

    showCardData(line) {
        const forms = this.l10nBrPos.session._l10n_br_forms_with_card || [];
        return forms.includes(line.payment_method_id?.fiscal_payment_form);
    },

    hasCardData(line) {
        return Boolean(line.card_authorization || line.card_brand || line.installments);
    },

    async editCardData(line) {
        const payload = await makeAwaitable(this.l10nBrDialog, CardDataPopup, {
            title: _t("Dados do cartão"),
            brands: this.l10nBrPos.session._l10n_br_card_brands || [],
            startingValues: {
                card_authorization: line.card_authorization,
                card_brand: line.card_brand,
                installments: line.installments,
            },
        });
        if (payload) {
            line.update(payload);
        }
    },
});
