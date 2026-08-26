# Copyright 2026 IT Brasil
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

# Forma de Pagamento (tPag) — tabela do leiaute da NF-e 4.00 após a NT 2023.004.
FISCAL_PAYMENT_FORM = [
    ("01", "01 - Dinheiro"),
    ("02", "02 - Cheque"),
    ("03", "03 - Cartão de Crédito"),
    ("04", "04 - Cartão de Débito"),
    ("05", "05 - Cartão da Loja (Private Label)"),
    ("10", "10 - Vale Alimentação"),
    ("11", "11 - Vale Refeição"),
    ("12", "12 - Vale Presente"),
    ("13", "13 - Vale Combustível"),
    ("14", "14 - Duplicata Mercantil"),
    ("15", "15 - Boleto Bancário"),
    ("16", "16 - Depósito Bancário"),
    ("17", "17 - Pagamento Instantâneo (PIX) - Dinâmico"),
    ("18", "18 - Transferência Bancária, Carteira Digital"),
    ("19", "19 - Programa de Fidelidade, Cashback, Crédito Virtual"),
    ("20", "20 - Pagamento Instantâneo (PIX) - Estático"),
    ("21", "21 - Crédito em Loja"),
    ("22", "22 - Pagamento Eletrônico não Informado (falha de hardware)"),
    ("90", "90 - Sem Pagamento"),
    ("99", "99 - Outros"),
]

# Formas que admitem o grupo <card>. Informá-lo fora desta lista é rejeição 963.
FISCAL_PAYMENT_FORM_WITH_CARD = (
    "03",
    "04",
    "10",
    "11",
    "12",
    "13",
    "15",
    "17",
    "18",
)

# Bandeira da operadora (tBand).
FISCAL_CARD_BRAND = [
    ("01", "Visa"),
    ("02", "Mastercard"),
    ("03", "American Express"),
    ("04", "Sorocred"),
    ("05", "Diners Club"),
    ("06", "Elo"),
    ("07", "Hipercard"),
    ("08", "Aura"),
    ("09", "Cabal"),
    ("99", "Outros"),
]
