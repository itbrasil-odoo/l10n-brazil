Torna a venda do Ponto de Venda fiscalmente válida no Brasil.

Sem este módulo, a fatura gerada por uma venda de PDV numa base com o
`l10n_br_account` instalado é lançada **sem documento fiscal**: sem
operação fiscal, sem tipo de documento e sem CFOP na linha. A fatura é
postada sem nenhum erro, o que faz a falha passar despercebida — a venda
simplesmente nunca vira documento fiscal.

Este módulo leva a operação fiscal para o PDV e a repassa à fatura, de
forma que a emissão (NF-e, NFS-e) encontre um documento completo.
