import {InvoiceButton} from "@point_of_sale/app/screens/ticket_screen/invoice_button/invoice_button";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";

patch(InvoiceButton.prototype, {
    get l10nBrFiscalReportId() {
        const order = this.props.order;
        if (!order || order.fiscal_document_state !== "autorizada") {
            return false;
        }
        const report =
            order.raw?.fiscal_document_report_id ?? order.fiscal_document_report_id;
        return typeof report === "object" ? report?.id : report;
    },

    get commandName() {
        return this.l10nBrFiscalReportId ? _t("Imprimir NF-e") : super.commandName;
    },

    /**
     * Com a nota autorizada, o balcão reimprime a NF-e; a fatura interna do
     * Odoo não é o documento que o cliente leva.
     */
    async _downloadInvoice() {
        const reportId = this.l10nBrFiscalReportId;
        if (!reportId) {
            return super._downloadInvoice(...arguments);
        }
        window.open(`/web/content/${reportId}?download=true`, "_blank");
    },
});
