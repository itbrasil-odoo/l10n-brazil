import {Component, useState} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";

export class CardDataPopup extends Component {
    static template = "l10n_br_pos.CardDataPopup";
    static components = {Dialog};
    static props = {
        title: String,
        brands: Array,
        startingValues: Object,
        getPayload: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            card_authorization: this.props.startingValues.card_authorization || "",
            card_brand: this.props.startingValues.card_brand || "",
            installments: this.props.startingValues.installments || "",
        });
    }

    confirm() {
        this.props.getPayload({
            card_authorization: this.state.card_authorization.trim() || false,
            card_brand: this.state.card_brand || false,
            installments: parseInt(this.state.installments, 10) || 0,
        });
        this.props.close();
    }
}
