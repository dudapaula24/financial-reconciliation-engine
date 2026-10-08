# Financial Reconciliation Engine

[English](README.md) | **Português (Brasil)**

Ferramenta de linha de comando em Python que concilia transações bancárias com registros contábeis, classifica cada registro por status de conciliação e gera um relatório em CSV.

> Todos os dados deste repositório são fictícios. Nomes como "Alpha Office Supplies" ou "Delta Logistics" são exemplos inventados.

## Visão geral

Conciliar significa verificar se cada movimentação do extrato bancário tem um lançamento correspondente na contabilidade, e vice-versa. Feito manualmente, é um trabalho repetitivo e sujeito a erros, principalmente quando valores se repetem ou quando as descrições são escritas de formas diferentes em cada lado.

Este projeto automatiza a primeira etapa desse trabalho. Ele lê dois arquivos CSV, valida os dados, forma pares de registros com regras simples e explicáveis, e informa o que foi conciliado, o que diverge em valor e o que ainda precisa de revisão manual.

## Início rápido

```bash
git clone https://github.com/dudapaula24/financial-reconciliation-engine.git
cd financial-reconciliation-engine
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate       # Linux / macOS
pip install -r requirements.txt

python -m reconciliation --bank data/bank_transactions.csv --accounting data/accounting_records.csv
```

## Funcionalidades

- **Validação de entrada** com mensagens de erro por linha: colunas obrigatórias, campos vazios, IDs duplicados, datas e valores.
- **Valores exatos**: armazenados como centavos inteiros, nunca como float.
- **Conciliação exata um para um** por data e valor, determinística quando há valores repetidos.
- **Detecção de divergência de valor** por data e descrição normalizada, com uma regra conservadora para casos ambíguos.
- **Quatro status**: `MATCHED`, `AMOUNT_MISMATCH`, `BANK_ONLY`, `ACCOUNTING_ONLY`.
- **Resumo** de itens e registros por status, exibido no terminal.
- **Relatório CSV** gravado com segurança: um relatório anterior é preservado se a gravação falhar.
- **Interface de linha de comando** com códigos de saída claros.

## Tecnologias

| Ferramenta | Uso |
|---|---|
| Python 3.11+ | Linguagem (`StrEnum` e pandas 3 exigem 3.11) |
| pandas 3 | Leitura de CSV e manipulação de dados tabulares |
| pytest | Testes automatizados |
| Biblioteca padrão do Python | `argparse`, `logging`, `decimal`, `enum`, `collections`, `tempfile`, `pathlib` |

- **Requisitos:** Python 3.11+ e pandas 3.
- **Testado com:** Python 3.13.13, pandas 3.0.6 e pytest 9.1.1 (as versões fixadas no `requirements.txt`).

## Como funciona

```
CSV do banco ─────────┐
                      ├─► leitura e validação ─► conciliação exata ─► divergência de valor ─► resultado ─┬─► resumo (terminal)
CSV da contabilidade ─┘                           (data + valor)       (apenas as sobras)                └─► relatório CSV
```

### Regras de conciliação

As regras são executadas nesta ordem. Cada etapa só recebe os registros que sobraram da anterior, então nenhum registro é usado duas vezes.

1. **Conciliação exata:** mesma `date` e mesmo `amount`. A descrição é ignorada. A conciliação é um para um: quando vários registros têm a mesma data e o mesmo valor, o primeiro registro bancário forma par com o primeiro registro contábil, o segundo com o segundo, seguindo a ordem dos arquivos.
2. **Divergência de valor:** entre as sobras, mesma `date` e mesma descrição normalizada, mas valores diferentes. A normalização remove espaços nas pontas, reduz espaços repetidos e ignora maiúsculas e minúsculas. Um par só é formado quando a data e a descrição aparecem **exatamente uma vez em cada lado**; registros ambíguos ficam para revisão manual.
3. **Sobras:** registros sem par se tornam `BANK_ONLY` ou `ACCOUNTING_ONLY`.

### Status

| Status | Significado | `difference` |
|---|---|---|
| `MATCHED` | Mesma data e mesmo valor nos dois lados | `0.00` |
| `AMOUNT_MISMATCH` | Mesma data e descrição, valores diferentes | valor do banco − valor da contabilidade |
| `BANK_ONLY` | Registro bancário não conciliado automaticamente | vazio |
| `ACCOUNTING_ONLY` | Registro contábil não conciliado automaticamente | vazio |

`BANK_ONLY` e `ACCOUNTING_ONLY` significam que o registro **não pôde ser conciliado automaticamente**, e não necessariamente que a transação não existe no outro lado.

### Decisões técnicas

- **Centavos inteiros em vez de float.** O float não representa exatamente muitos valores decimais (`0.29 * 100` resulta em `28.999999999999996`). Os valores são lidos como texto com `Decimal` e armazenados como inteiros, então as comparações são exatas.
- **Filas em vez de um `merge` simples.** Um merge por data e valor combina cada registro com todos os outros que têm a mesma chave, e um registro contábil poderia formar par com dois registros bancários. Em vez disso, cada chave tem uma fila FIFO (o primeiro a entrar é o primeiro a sair), e o candidato é removido da fila quando é usado.
- **Regra conservadora para descrições.** Comparar descrições é uma heurística, então, em casos ambíguos, o sistema prefere deixar os registros para revisão a tentar adivinhar.
- **Inteiros com suporte a ausentes no resultado.** No pandas, um valor ausente transforma uma coluna de inteiros comum em float; o tipo `Int64` mantém os valores como inteiros.
- **Gravação segura do relatório.** O relatório é gravado em um arquivo temporário na mesma pasta e só depois substitui o arquivo final com `os.replace`, então uma falha nunca deixa um relatório gravado pela metade.

## Formato de entrada

Os dois arquivos usam o mesmo formato:

```csv
id,date,description,amount
B001,2026-09-01,Alpha Office Supplies,-350.00
```

| Coluna | Regra |
|---|---|
| `id` | Obrigatório, único dentro do arquivo |
| `date` | Obrigatório, `AAAA-MM-DD` |
| `description` | Obrigatório |
| `amount` | Obrigatório, ponto como separador decimal, no máximo duas casas decimais, sem símbolo de moeda nem separador de milhar. Entradas são positivas e saídas negativas, com a mesma convenção nos dois arquivos |

Colunas extras são permitidas e ignoradas. Os arquivos são lidos em UTF-8.

## Uso da CLI

```bash
python -m reconciliation --bank CSV_DO_BANCO --accounting CSV_DA_CONTABILIDADE [--output CSV_DO_RELATORIO]
```

| Argumento | Obrigatório | Descrição |
|---|---|---|
| `--bank` | sim | Arquivo CSV de transações bancárias |
| `--accounting` | sim | Arquivo CSV de registros contábeis |
| `--output` | não | Arquivo do relatório (padrão: `output/reconciliation_result.csv`) |

| Código de saída | Significado |
|---|---|
| `0` | Sucesso |
| `1` | Arquivo de entrada não encontrado, dados de entrada inválidos ou relatório não pôde ser gravado |
| `2` | Argumentos de linha de comando inválidos |

O resumo é exibido na saída padrão; mensagens de log e erros vão para a saída de erro.

## Exemplo de saída

Executando o comando do início rápido com os arquivos de exemplo em `data/`:

```text
INFO: Loaded 6 records from data/bank_transactions.csv
INFO: Loaded 5 records from data/accounting_records.csv
Reconciliation summary
         status  items  bank_records  accounting_records
        MATCHED      3             3                   3
AMOUNT_MISMATCH      1             1                   1
      BANK_ONLY      2             2                   0
ACCOUNTING_ONLY      1             0                   1
Total: 7 items, 6 bank records, 5 accounting records
Report written to output/reconciliation_result.csv
```

`items` conta as linhas do resultado (um par é um item); `bank_records` e `accounting_records` contam os registros de entrada, então os totais batem com o tamanho de cada arquivo.

Relatório gerado:

```csv
status,bank_id,accounting_id,date,bank_description,accounting_description,bank_amount,accounting_amount,difference
MATCHED,B001,A001,2026-09-01,Alpha Office Supplies,Alpha Office Supplies,-350.00,-350.00,0.00
MATCHED,B002,A002,2026-09-02,BETA CONSULTING,Beta Consulting,1200.50,1200.50,0.00
MATCHED,B005,A005,2026-09-08,Epsilon Cleaning Services,Epsilon Cleaning Services,-200.00,-200.00,0.00
AMOUNT_MISMATCH,B004,A004,2026-09-05,DELTA LOGISTICS,Delta Logistics,1000.00,990.00,10.00
BANK_ONLY,B003,,2026-09-03,Monthly Bank Fee,,-15.00,,
BANK_ONLY,B006,,2026-09-08,Epsilon Cleaning Services,,-200.00,,
ACCOUNTING_ONLY,,A003,2026-09-04,,Gamma Software License,,-89.90,
```

Repare no `B006`: ele tem a mesma data, descrição e valor que o `B005`, mas o único registro contábil correspondente (`A005`) já foi usado, então o `B006` fica sem conciliação.

Dados inválidos são informados com o arquivo e a linha. Por exemplo, um arquivo `bank_with_errors.csv` cuja terceira linha tem `abc` como valor:

```text
ERROR: Invalid input data: bank_with_errors.csv: Invalid amount on line(s): 3
```

## Executando os testes

```bash
pytest          # executa todos os testes
pytest -v       # uma linha por teste
```

Os testes cobrem:

- **Leitura:** arquivos válidos, cada regra de validação e casos-limite na conversão de valores (`"0.29"`, `"NaN"`, `"10.005"`).
- **Conciliação:** pares um para um, duplicidades, determinismo pela ordem dos arquivos, normalização de descrições, casos ambíguos e o dataset de exemplo completo.
- **Resultado e resumo:** tipos das colunas, cada registro aparecendo exatamente uma vez e totais sem contagem duplicada.
- **Relatório:** formatação decimal (incluindo negativos como `-0.05`), campos vazios e preservação do relatório anterior quando a gravação falha.
- **CLI:** execuções completas, códigos de saída, mensagens de erro e execução como `python -m reconciliation`.

## Estrutura do projeto

```text
financial-reconciliation-engine/
├── data/                    # arquivos de entrada fictícios
├── reconciliation/
│   ├── __main__.py          # ponto de entrada de python -m reconciliation
│   ├── cli.py               # argumentos, logging e códigos de saída
│   ├── loader.py            # leitura, validação e conversão para centavos
│   ├── matcher.py           # regras de conciliação exata e divergência de valor
│   ├── reconciler.py        # status e resultado consolidado
│   ├── summary.py           # contagens por status
│   └── report.py            # formatação de valores e exportação CSV
├── tests/                   # testes com pytest
├── pytest.ini
└── requirements.txt
```

## Limitações

- A conciliação exata exige datas e valores idênticos; não há tolerância de data nem de valor.
- Comparar descrições é uma heurística. Pode gerar falsos positivos (dois pagamentos diferentes ao mesmo fornecedor no mesmo dia) e falsos negativos (acentos, pontuação, abreviações e prefixos bancários não são normalizados).
- Quando vários registros têm a mesma data e descrição, nenhum par de divergência é formado e eles ficam para revisão manual.
- A conciliação exata é executada primeiro e ignora descrições, então pode usar um registro que seria uma divergência de valor mais plausível.
- Não há limite para diferenças: uma diferença de 0.01 e uma de 1000000.00 recebem o mesmo status.
- Apenas pares um para um são suportados; um pagamento que cobre vários lançamentos não é reconhecido.
- Assume-se uma única moeda e um formato de CSV fixo.
- O relatório é gravado em UTF-8 sem BOM, então alguns programas de planilha podem exibir caracteres acentuados incorretamente.
- Todos os dados são processados em memória. O desempenho não foi medido.

## Melhorias futuras

- Tolerâncias configuráveis de data e de valor.
- Escolha do valor mais próximo quando houver vários candidatos.
- Normalização de descrições configurável.
- Outros formatos de relatório.
- Imagem Docker.
- Interface de usuário.

## Autoria

Desenvolvido por [dudapaula24](https://github.com/dudapaula24).

