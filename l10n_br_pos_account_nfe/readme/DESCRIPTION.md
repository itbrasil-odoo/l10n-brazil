Módulo-ponte entre o `l10n_br_pos_nfe` e o `l10n_br_account_nfe`. Instala-se
sozinho quando os dois estão presentes.

O `l10n_br_pos_nfe` leva à NF-e um grupo `detPag` por pagamento recebido no
caixa, com a forma de pagamento e os dados do cartão. O `l10n_br_account_nfe`
calcula o mesmo campo a partir do modo de pagamento da fatura e, quando a
fatura não tem modo de pagamento, declara "sem pagamento" (`tPag` 90). A fatura
da venda de balcão não tem modo de pagamento, então com os dois módulos
instalados a nota saía sem a forma de pagamento real.

Com este módulo, o documento fiscal de uma fatura que vem de um pedido do PDV
mantém os pagamentos do caixa. As demais faturas seguem a regra do
`l10n_br_account_nfe`, sem mudança.
