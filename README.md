# Empório da Música — Agente de Atendimento (protótipo)

> Desafio Técnico — AI Engineer @ Artefact

Agente de mensagens em Python para a **Empório da Música**, loja fictícia de
instrumentos musicais em Campo Grande/MS. Responde clientes cruzando dois
tipos de contexto — **dados estruturados** (`data/*.csv`: produtos, pedidos,
clientes, promoções) e **políticas da loja** (`data/politicas_da_loja.pdf`) —
decidindo sozinho quando consultar cada um, e lida com perguntas fora de
escopo.

## Como rodar

Requer **Python 3.10+**.

```bash
git clone <url-do-repo>
cd emporio-da-musica-agent
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # edite e cole sua GEMINI_API_KEY (grátis em aistudio.google.com/apikey)
python cli.py
```

Comandos no chat: `/novo` reinicia a conversa, `/salvar` salva o histórico em
`conversations/` (fora do controle de versão), `/sair` encerra e salva. Os
exemplos "oficiais" do desafio estão curados em [`examples/`](examples/).

Testes: `python -m unittest discover -s tests -v`

Modelo padrão: `gemini-3.5-flash-lite`. Para trocar, defina `GEMINI_MODEL` no
`.env`.

## Decisões técnicas

### Framework / abordagem do agente

**Híbrido**, com loop manual de tool-use (`src/agent/core.py`): **function
calling** sobre um SQLite em memória para dados estruturados e mutáveis
(produto, preço, estoque, status de pedido) e **RAG leve por busca lexical
(BM25)**, sem embeddings, sobre o PDF de políticas
(`src/agent/policy_search.py`) — um manual de 8 páginas e 10 seções não
justifica o custo/complexidade de um índice vetorial; um chunk por seção,
indexado com BM25 e um stemmer leve (necessário para casar "devolver" com
"devolução" no manual), resolveu bem as perguntas testadas. O próprio modelo
decide, a cada mensagem, quais ferramentas chamar (zero, uma ou várias) com
base nas descrições das ferramentas e no system prompt (`src/agent/prompts.py`,
que fixa persona, escopo e a regra de nunca inventar preço/estoque/status/
política) — não há roteador manual antes do Gemini, o que é o teste real de
"saber quando consultar dados vs. políticas". Preferi ferramentas
parametrizadas e previsíveis (`search_products`, `get_order_status` etc., em
`src/agent/tools.py`) a um agente de SQL livre, pelo risco de o modelo
alucinar uma coluna, gerar uma query lenta ou vazar dados de outro cliente. O
loop de chamada de ferramentas foi escrito à mão (`automatic_function_calling`
do SDK desligado) para deixar explícito como o histórico é montado e garantir
que um par `function_call`/`function_response` nunca seja cortado ao aparar
histórico antigo — e inclui retentativa automática (`HttpRetryOptions`) em
erros transitórios do provedor (503 etc.), comuns no tier gratuito.

### Modelo e provedor

**Google Gemini** (`google-genai`, SDK oficial), modelo `gemini-3.5-flash-lite`.
Comecei com a API da Anthropic (Claude Sonnet) e migrei por **custo**: o
Google AI Studio tem tier gratuito genuíno (sem cartão de crédito), o que
permite reexecutar e regerar os exemplos deste desafio quantas vezes forem
necessárias sem gastar nada — a conta de teste da Anthropic, paga desde a
primeira chamada, ficou sem crédito no meio do desenvolvimento (ver "Uso de
assistentes de IA"). A escolha do modelo específico veio de teste real contra
a API, não de documentação/memória: `gemini-2.5-flash` (pedido inicialmente)
retorna `404 NOT_FOUND` para chaves novas; o substituto sugerido pelo próprio
erro, `gemini-3.6-flash`, tem cota gratuita de só 20 requisições/dia — pouco
até para a bateria de testes deste desafio; `gemini-3.5-flash-lite` funcionou
de ponta a ponta sem esbarrar em cota, inclusive para regerar os 5 exemplos.
Trocar de modelo é só uma variável de ambiente (`GEMINI_MODEL`), sem mudar
código.

### Interface de interação

**CLI** (`cli.py`), com comandos simples (`/novo`, `/salvar`, `/sair`). Optei
por isso porque o foco do desafio é o agente funcionando corretamente, não a
interface — uma UI web ou notebook adicionaria superfície de implementação
sem testar melhor o comportamento do agente (decisão de tool-use, retrieval
de políticas, tratamento de casos especiais).

### Persistência do histórico de conversa

Em memória durante a sessão do processo, mantendo o histórico completo por
"turno" para nunca cortar um par `function_call`/`function_response` ao
aparar histórico antigo (`max_history_turns` em `src/agent/config.py`). Não
implementei persistência em banco entre execuções porque nada no desafio pede
retomar uma conversa entre execuções diferentes do processo. Ainda assim, o
CLI salva um log em Markdown de cada sessão em `conversations/` (fora do
controle de versão) ao sair — útil para depuração e revisão de conversas
passadas, mas não um requisito de produto em si.

### Tratamento dos dados

Limpeza leve ao carregar os CSVs para o SQLite em memória
(`src/agent/store_data.py`): conversão de tipos (preço/estoque para número),
normalização de espaços em branco e de `status` (minúsculo), strings vazias
viram `NULL`. Produtos com status `discontinued` ou `coming_soon`
**não são escondidos** das buscas — o agente precisa poder explicar a
situação ao cliente em vez de simplesmente informar "não encontrado". O
preço com desconto de uma promoção ativa é pré-calculado em `store_data.py`
(`price_with_promotion_brl`), para não deixar essa conta a cargo do modelo.

Justificativas mais detalhadas, com trade-offs considerados, estão nos
comentários do código correspondente a cada decisão.

## Estrutura do projeto

```
emporio-da-musica-agent/
├── cli.py                        # ponto de entrada do chat no terminal
├── data/                         # CSVs + PDF de políticas fornecidos no desafio
├── src/agent/
│   ├── config.py                 # caminhos, modelo, limites do loop de tool-use
│   ├── store_data.py             # CSVs -> SQLite em memória + funções de consulta
│   ├── policy_search.py          # PDF -> chunks por seção + índice BM25
│   ├── tools.py                  # schemas de ferramentas (function calling) + dispatch
│   ├── prompts.py                # persona / system prompt
│   └── core.py                   # loop de conversa e chamada de ferramentas
├── tests/                        # testes da camada de dados e de busca de políticas
├── examples/                     # 5 conversas de exemplo (entregável do desafio)
└── scripts/generate_examples.py  # gera examples/ rodando o agente de verdade
```

## Exemplos de conversa

Ver [`examples/`](examples/) — 5 transcrições reais (`gemini-3.5-flash-lite`),
regeráveis com `python scripts/generate_examples.py`:

1. [`01_busca_por_categoria_e_preco.md`](examples/01_busca_por_categoria_e_preco.md) — busca por categoria e preço.
2. [`02_horario_e_endereco.md`](examples/02_horario_e_endereco.md) — informações gerais da loja (política).
3. [`03_preco_produto_especifico.md`](examples/03_preco_produto_especifico.md) — preço/estoque de um produto.
4. [`04_devolucao_e_status_pedido.md`](examples/04_devolucao_e_status_pedido.md) — política de devolução **+** status de pedido na mesma conversa.
5. [`05_fora_de_escopo.md`](examples/05_fora_de_escopo.md) — perguntas fora do escopo da loja.

## Limitações conhecidas

- **Sem autenticação real de cliente** — `get_order_status` aceita nome como
  busca; numa versão real (WhatsApp), o telefone do cliente validaria a
  identidade antes de expor dados do pedido.
- **Retrieval lexical, não semântico** — BM25 + stemming leve resolve as
  perguntas testadas, mas paráfrases muito distantes do texto podem falhar.
- **Sem streaming** e **sem persistência entre execuções do processo**.
- **Sem avaliação automatizada da qualidade das respostas** — os testes
  cobrem só a camada determinística (dados e busca).

## Uso de assistentes de IA

Desenvolvido de ponta a ponta com o **Claude Code** (VS Code, modelo Sonnet
5) como par de desenvolvimento: leitura do desafio e dos dados, decisões de
arquitetura discutidas e revisadas comigo (não aceitas às cegas), escrita do
código, e geração dos exemplos via `scripts/generate_examples.py` contra a
API real do Gemini. A troca de provedor (Anthropic → Gemini) foi decidida por
mim após a conta de teste da Anthropic ficar sem crédito; a implementação
usou introspecção do SDK `google-genai` instalado (em vez de confiar em
memória/docs desatualizadas) para evitar alucinação de API. Commits feitos
incrementalmente ao longo do desenvolvimento, refletindo o progresso real.
