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

- **Agente híbrido, loop manual de tool-use** (`src/agent/core.py`): function
  calling sobre SQLite (dados estruturados, carregado dos CSVs em memória) +
  RAG leve sobre o PDF (políticas). O próprio Gemini decide, a cada mensagem,
  quais ferramentas chamar — sem roteador manual. Loop implementado à mão
  (não `automatic_function_calling`) para deixar explícito como o histórico é
  montado e nunca cortar um par `function_call`/`function_response`.
  Ferramentas parametrizadas (`src/agent/tools.py`) em vez de SQL livre, para
  evitar alucinação de query. Retentativa automática (`HttpRetryOptions`) em
  erros transitórios (503 etc.), comuns no tier gratuito.
- **LLM: Google Gemini** (`google-genai`), modelo `gemini-3.5-flash-lite`.
  Migrado da API da Anthropic por custo (tier gratuito genuíno vs. paga desde
  a primeira chamada — ver detalhes em "Uso de assistentes de IA"). Escolha
  do modelo testada na prática: `gemini-2.5-flash` retorna 404 para chaves
  novas; `gemini-3.6-flash` tem cota gratuita baixa (20 req/dia); `-lite`
  funcionou sem esbarrar em cota.
- **Retrieval de políticas: chunking por seção + BM25, sem embeddings**
  (`src/agent/policy_search.py`). O manual tem 8 páginas e 10 seções
  numeradas — overkill usar embeddings/vetor. Um chunk por seção de primeiro
  nível, indexado com BM25 e um stemmer leve (corta tokens em 5 caracteres,
  necessário para casar "devolver" com "devolução"). A seção sobre tom/fluxo
  de atendimento foi incorporada direto no system prompt, não só na busca.
- **Prompt único** (`src/agent/prompts.py`): persona, escopo, regra de nunca
  inventar preço/estoque/status/política, e tratamento de casos especiais
  (esgotado, descontinuado, pedido não encontrado etc.).
- **Histórico em memória** por processo, sem persistência em banco entre
  execuções (fora do escopo do desafio); log em Markdown salvo por sessão.

Justificativas completas de cada decisão (com trade-offs considerados) estão
comentadas no código correspondente.

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
