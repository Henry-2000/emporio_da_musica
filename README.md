# Empório da Música — Agente de Atendimento (protótipo)

> Desafio Técnico — AI Engineer @ Artefact

Protótipo em Python de um agente de mensagens de texto para a **Empório da
Música**, loja fictícia de instrumentos musicais em Campo Grande/MS. O agente
responde clientes com base em dois tipos de contexto:

- **Dados estruturados** (`data/*.csv`): produtos, pedidos, clientes, promoções.
- **Políticas da loja** (`data/politicas_da_loja.pdf`): horário, pagamento,
  trocas/devoluções, frete, garantia, privacidade.

e sabe decidir sozinho quando consultar cada um (ou os dois), lidando também
com perguntas fora do escopo da loja.

## Sumário

- [Como rodar](#como-rodar)
- [Decisões técnicas](#decisões-técnicas)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Exemplos de conversa](#exemplos-de-conversa)
- [Limitações conhecidas e próximos passos](#limitações-conhecidas-e-próximos-passos)
- [Uso de assistentes de IA](#uso-de-assistentes-de-ia)

## Como rodar

Requer **Python 3.10+**.

```bash
# 1. Clone e entre na pasta do projeto
git clone <url-do-repo>
cd emporio-da-musica-agent

# 2. Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows (PowerShell/cmd)

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure a chave da API do Gemini
cp .env.example .env             # Windows: copy .env.example .env
# edite .env e cole sua GEMINI_API_KEY (chave gratuita em aistudio.google.com/apikey)

# 5. Rode o chat
python cli.py
```

Dentro do chat: `/novo` reinicia a conversa, `/salvar` salva o histórico atual
em `conversations/`, `/sair` encerra (a conversa também é salva automaticamente
ao sair). `conversations/` é só um log de sessões reais e fica fora do
controle de versão (`.gitignore`) — os exemplos "oficiais" do desafio estão
curados em [`examples/`](examples/).

Para rodar os testes automatizados (camada de dados e busca de políticas):

```bash
python -m unittest discover -s tests -v
```

Por padrão o agente usa `gemini-3.5-flash-lite`. Para trocar de modelo, defina
`GEMINI_MODEL` no `.env` — veja `.env.example`.

## Decisões técnicas

### Framework / abordagem do agente: híbrido, com loop manual de tool-use

O agente é **híbrido**, como sugerido no enunciado:

- **Function calling** sobre um banco SQLite (carregado dos CSVs em memória a
  cada execução) para tudo que é fato estruturado e mutável: produto, preço,
  estoque, promoção ativa, status de pedido.
- **RAG leve** (busca lexical, sem embeddings) sobre o PDF de políticas para
  regras e procedimentos: trocas/devoluções, formas de pagamento, frete,
  garantia, endereço/horário da loja.

O próprio modelo decide, a cada mensagem, quais ferramentas chamar (zero, uma
ou várias, inclusive em sequência) com base nas descrições das ferramentas e
nas instruções do system prompt — não há um roteador/classificador manual
antes do Gemini. Isso é o teste real do "saber quando consultar dados e
quando consultar políticas" pedido no desafio.

O loop de chamada de ferramentas (`src/agent/core.py`) foi implementado **na
mão**, sobre `client.models.generate_content`, com a chamada automática de
função do SDK (`automatic_function_calling`) explicitamente desligada.
Motivo: para um protótipo pequeno como este, o loop manual deixa explícito —
e fácil de revisar em code review — exatamente como o histórico é montado,
como os resultados de ferramenta viram `function_response`, e como o corte de
histórico antigo nunca quebra um par `function_call`/`function_response` (ver
`ConversationAgent._history_contents`). Também deixa o despacho de fato
(`tools.execute_tool`) totalmente agnóstico de provedor — só quem monta a
mensagem no formato de cada API muda, o que se confirmou na prática ao trocar
de provedor (ver "LLM e provedor" abaixo e o histórico do git).

**Retentativa em erro transitório.** O `google-genai` não reenvia nada por
padrão — sem configurar `retry_options` explicitamente, um `503` de alta
demanda (comum no tier gratuito) sobe como exceção já na primeira tentativa,
inclusive para uma mensagem trivial como "Boa tarde" (bug real encontrado
durante o desenvolvimento, não hipotético). `ConversationAgent` passa
`HttpRetryOptions()` na construção do cliente para ligar a política padrão do
próprio SDK: até 5 tentativas com backoff exponencial + jitter (1s a 60s)
para 408/429/500/502/503/504. Só depois de esgotar essas tentativas o erro
chega ao usuário — e mesmo assim como mensagem genérica (o `cli.py` loga o
erro real em stderr, não expõe o traceback no chat).

**Por que não um "agente de SQL" com acesso livre?** O enunciado lista essa
opção, mas optei por expor **funções parametrizadas e previsíveis**
(`search_products`, `get_order_status` etc. — ver `src/agent/tools.py`) em vez
de deixar o modelo escrever SQL arbitrário. Com poucas tabelas e consultas bem
conhecidas de antemão (buscar produto, checar promoção, status de pedido), o
ganho de flexibilidade do SQL livre não compensa o risco de o modelo
alucinar uma coluna, gerar uma query lenta/perigosa, ou vazar dados de outro
cliente. Fica registrado como algo a reconsiderar se o catálogo de perguntas
crescer muito (ver Limitações).

### LLM e provedor: Google Gemini, `gemini-3.5-flash-lite`

O projeto começou sobre a API da Anthropic (Claude Sonnet) e foi **migrado
para a API do Gemini** depois — a motivação principal foi **custo**: o Google
AI Studio oferece um tier gratuito genuíno (sem cartão de crédito, sem
crédito pago para gastar), o que permite prototipar, testar e regenerar os
exemplos deste README quantas vezes forem necessárias sem gastar nada — algo
que esbarrou num problema real durante o desenvolvimento com a API da
Anthropic (paga desde a primeira chamada; ver "Uso de assistentes de IA" para
o relato completo). Para um desafio de portfólio/processo seletivo, onde o
projeto pode ser reexecutado e reavaliado várias vezes, essa diferença
importa mais do que para um produto em produção com orçamento já aprovado.

- **Provedor**: API do Gemini (`google-genai`, o SDK oficial atual — não o
  pacote `google-generativeai`, descontinuado).
- **Modelo**: `gemini-3.5-flash-lite` é o padrão. Essa escolha específica só
  ficou clara testando de verdade contra a API (não por documentação/memória
  — modelos e cotas mudam rápido demais para confiar em conhecimento
  desatualizado):
  - `gemini-2.5-flash` (pedido inicialmente) devolve `404 NOT_FOUND` —
    "This model ... is no longer available to new users".
  - O substituto que a própria mensagem de erro recomenda,
    `gemini-3.6-flash`, funciona, mas o tier gratuito dele tem cota de
    **20 requisições/dia por projeto** — a própria bateria de testes deste
    desafio (alguns smoke tests + os 5 exemplos, cada um com 2 turnos) já
    estoura esse limite, então não é um modelo viável para prototipar sem
    custo, mesmo sendo "gratuito" em tese.
  - `gemini-3.5-flash-lite` (nível "lite") funcionou de ponta a ponta sem
    esbarrar em cota nenhuma vez durante todo o desenvolvimento — inclusive
    para regerar os 5 exemplos em `examples/` (ver mais abaixo). Nível
    "lite" tende a ter cota gratuita bem mais generosa que o "flash" cheio,
    o que faz sentido para o caso de uso daqui: várias chamadas de
    ferramenta por mensagem, custo/latência importam mais que ter o modelo
    mais "raciocinador" da linha.
  - Nos testes manuais feitos durante o desenvolvimento (não uma avaliação
    formal — ver Limitações), `gemini-3.5-flash-lite` seguiu bem as
    instruções de escopo/tom e encadeou corretamente duas ferramentas na
    mesma resposta (política de devolução + status de um pedido real — ver
    `examples/04_devolucao_e_status_pedido.md`).
  - Trocar de modelo é uma variável de ambiente (`GEMINI_MODEL`), sem mudar
    código — útil já que a disponibilidade de modelo nessa API mudou de
    verdade dentro desta mesma sessão de desenvolvimento.

### Arquitetura de retrieval: chunking por seção + BM25 (sem embeddings)

O manual de políticas tem só 8 páginas e uma estrutura numerada de 10 seções
(`1. Sobre a Empório da Música` … `10. Disposições Finais`). Para um documento
desse tamanho, uma API de embeddings ou um banco vetorial seriam overkill —
optei por:

1. Extrair o texto do PDF com `pypdf` no modo `extraction_mode="layout"`
   (preserva parágrafos e tabelas — o modo padrão devolve uma palavra por
   linha nesse PDF específico, que aparentemente foi gerado com uma
   caixa de texto por palavra).
2. Dividir o texto em **um chunk por seção de primeiro nível** (10 chunks),
   via regex ancorada em início de linha sem indentação — o que também evita
   confundir cabeçalho de seção com itens de lista numerados dentro do texto
   (ex.: o passo-a-passo "1. Saudação, 2. Entendimento..." da seção 7.2).
3. Indexar os chunks com **BM25** (`rank-bm25`), com uma normalização leve:
   minúsculas, remoção de acentos, e um "poor man's stemmer" (corta tokens
   longos para os 5 primeiros caracteres). Isso importa na prática: a
   pergunta do cliente usa "**devolver**" e o manual usa "**devolução**" — sem
   esse corte, BM25 puro não acha nenhuma palavra em comum e erra a seção
   (testado e comparado em `tests/test_policy_search.py`).
4. `search_policies(query)` devolve os até 2 chunks mais relevantes (ou uma
   lista vazia se nada bateu — sinal para o agente dizer "não sei" em vez de
   inventar).

A seção 7 do manual ("Atendimento via WhatsApp") é tratada como um **caso à
parte**: ela descreve como o atendente (humano ou virtual) deve se comportar,
não uma regra para citar ao cliente. Por isso seu conteúdo (tom de voz,
escopo, fluxo de atendimento, situações especiais) foi incorporado
diretamente no **system prompt** (`src/agent/prompts.py`) em vez de ficar só
disponível via busca — comportamento essencial não deveria depender do
ranking de uma busca lexical para ser seguido de forma consistente.

### Estratégia de prompt

Um único system prompt fixo (`src/agent/prompts.py`) define: persona e tom,
escopo da loja (só instrumentos, sem acessórios), a regra inegociável de
nunca inventar preço/estoque/status/desconto/política sem consultar a
ferramenta certa, quando usar cada ferramenta, e como tratar os "casos
especiais" descritos no manual (produto esgotado, descontinuado, promoção
vencida, pedido não encontrado, reclamação). O modelo decide sozinho, a cada
turno, se e quais ferramentas chamar — não há prompt separado por tipo de
pergunta.

### Persistência de histórico

Em memória durante a sessão do processo (`ConversationAgent` mantém o
histórico completo, por "turno", para nunca cortar um par
`function_call`/`function_response` ao aparar histórico antigo — ver
`max_history_turns` em `src/agent/config.py`). O CLI também salva um log em
Markdown de cada sessão em `conversations/` ao sair, útil para depuração e
para revisar conversas passadas — mas não é um requisito de produto em si
(nada no enunciado pede retomar uma conversa entre execuções diferentes do
processo), então não implementei persistência em banco/arquivo entre
processos.

### Tratamento de dados

Limpeza leve, feita ao carregar os CSVs para o SQLite em memória
(`src/agent/store_data.py`): conversão de tipos (preço/estoque para
número), normalização de espaços em branco e de `status` (minúsculo),
strings vazias viram `NULL`. Produtos com status `discontinued` ou
`coming_soon` **não são escondidos** das buscas — o agente precisa poder
explicar a situação ao cliente (ver seção "Situações especiais" do manual),
em vez de simplesmente informar "não encontrado". O preço com desconto de
uma promoção ativa é calculado uma vez em `store_data.py`
(`price_with_promotion_brl`) para não deixar essa conta a cargo do modelo.

## Estrutura do projeto

```
emporio-da-musica-agent/
├── cli.py                     # ponto de entrada do chat no terminal
├── data/                      # CSVs + PDF de políticas fornecidos no desafio
├── src/agent/
│   ├── config.py              # caminhos, modelo, limites do loop de tool-use
│   ├── store_data.py          # CSVs -> SQLite em memória + funções de consulta
│   ├── policy_search.py       # PDF -> chunks por seção + índice BM25
│   ├── tools.py                # schemas de ferramentas (function calling) + dispatch
│   ├── prompts.py             # persona / system prompt
│   └── core.py                 # loop de conversa e chamada de ferramentas
├── tests/                     # testes da camada de dados e de busca de políticas
├── examples/                  # 5 conversas de exemplo (entregável do desafio)
├── scripts/generate_examples.py  # gera examples/ rodando o agente de verdade
└── requirements.txt
```

## Exemplos de conversa

Ver a pasta [`examples/`](examples/) — 5 conversas reais com o agente
(`gemini-3.5-flash-lite`, via `cli.py`/`scripts/generate_examples.py`),
cobrindo os cenários do desafio. São transcrições de chamadas reais à API do
Gemini contra os dados deste projeto, não conversas inventadas — rode
`python scripts/generate_examples.py` (com `GEMINI_API_KEY` configurada) para
regerá-las a qualquer momento.

1. [`01_busca_por_categoria_e_preco.md`](examples/01_busca_por_categoria_e_preco.md)
   — busca no catálogo por categoria e faixa de preço.
2. [`02_horario_e_endereco.md`](examples/02_horario_e_endereco.md) —
   informações gerais da loja (política).
3. [`03_preco_produto_especifico.md`](examples/03_preco_produto_especifico.md)
   — consulta de preço/estoque de um produto específico.
4. [`04_devolucao_e_status_pedido.md`](examples/04_devolucao_e_status_pedido.md)
   — **cenário não trivial**: aplica a política de devolução E consulta o
   status de um pedido real na mesma conversa.
5. [`05_fora_de_escopo.md`](examples/05_fora_de_escopo.md) — pergunta fora do
   escopo da loja (acessório que não vendemos, e uma pergunta sem nenhuma
   relação com a loja).

## Limitações conhecidas e próximos passos

- **Sem autenticação real de cliente.** `get_order_status` aceita nome do
  cliente como uma das formas de busca, mas qualquer pessoa poderia pedir o
  pedido de outra só sabendo o nome. Numa versão real, o canal (WhatsApp)
  teria o telefone do cliente disponível para cruzar com `customers.csv`
  antes de expor detalhes de pedido — não implementei isso por não haver um
  "número de telefone de quem está digitando" disponível num CLI de
  terminal.
- **Retrieval lexical, não semântico.** BM25 + stemming leve resolve bem as
  perguntas testadas, mas uma pergunta com vocabulário muito distante do
  texto do manual (paráfrase forte, sinônimo raro) pode não recuperar a
  seção certa. Com mais tempo, uma comparação direta entre esse índice BM25
  e um índice de embeddings (ex.: Voyage AI) sobre o mesmo conjunto de
  perguntas de teste ajudaria a decidir se vale a complexidade extra —
  para um manual de 8 páginas, eu ainda apostaria que não vale.
- **Sem streaming.** Respostas são curtas o bastante (poucas centenas de
  tokens) para não esbarrar em timeout, mas numa UI real (não-CLI) streaming
  melhoraria a percepção de latência.
- **Persistência só em memória/log local.** Não há retomada de conversa entre
  execuções do processo, nem multiusuário (cada execução do CLI é uma sessão
  isolada). Para um canal de WhatsApp real, o histórico precisaria ficar em
  um banco por número de telefone.
- **Sem avaliação automatizada do agente em si.** Os testes automatizados
  (`tests/`) cobrem a camada determinística (dados e busca), não a qualidade
  das respostas geradas pelo modelo. Com mais tempo, escreveria um pequeno
  conjunto de "evals" (perguntas + critério de aceite) rodado contra o
  agente de ponta a ponta, para pegar regressões de prompt.
- **Preço com múltiplas promoções.** `promotions.csv` permite, em teoria, mais
  de uma promoção ativa por produto ao mesmo tempo; hoje eu pego a de maior
  desconto (`store_data._attach_promotion`), já que o manual diz que
  promoções não são cumulativas — mas o CSV fornecido nunca teve esse caso
  na prática, então não há teste automatizado específico para ele.
- **Disponibilidade e cota de modelo mudam rápido.** Durante o desenvolvimento,
  um modelo pedido explicitamente (`gemini-2.5-flash`) ficou indisponível
  para chaves novas, e o substituto sugerido pela própria API
  (`gemini-3.6-flash`) tinha cota gratuita baixa demais para uso real (20
  requisições/dia). Não há verificação automática de "esse modelo ainda
  existe e tem cota suficiente" no código — se `GEMINI_MODEL` apontar para um
  modelo desativado/sem cota, o erro só aparece na primeira chamada. Com mais
  tempo, valeria checar `client.models.list()` na inicialização e falhar
  cedo com uma mensagem clara, em vez de deixar o erro estourar no meio de
  uma conversa com o cliente.

## Uso de assistentes de IA

Este projeto foi desenvolvido com o **Claude Code** (extensão VS Code, usando
o modelo Sonnet 5) como par de desenvolvimento, de ponta a ponta — da leitura
inicial do desafio e dos dados até este README. Descrevendo o workflow com
transparência, como pedido no enunciado:

- **Leitura e exploração dos materiais**: pedi ao Claude Code para ler o PDF
  do desafio e o manual de políticas diretamente (via sua ferramenta de
  leitura de PDF) e inspecionar os CSVs (linhas, tipos de dado, valores
  únicos de colunas como `status`) antes de decidir qualquer coisa de
  arquitetura — isso pegou cedo, por exemplo, que `products.status` tem um
  valor `coming_soon` além de `active`/`discontinued`, o que mudou como o
  agente trata "produto não encontrado" (ver Situações Especiais no system
  prompt).
- **Decisões de arquitetura em conjunto**: as decisões técnicas mais
  importantes (localização do projeto, framework de retrieval das políticas)
  foram levantadas como pergunta explícita pelo Claude Code antes de
  implementar, com opções e trade-offs — não foram escolhidas
  silenciosamente. As demais decisões (SQLite vs. pandas, loop manual vs.
  `tool_runner`, não expor SQL livre ao modelo) foram propostas pelo Claude
  Code e revisadas por mim durante o desenvolvimento; a justificativa de
  cada uma está nas seções acima e nos comentários do código correspondente.
- **Iteração orientada a teste real, não só "parece certo"**: a decisão de
  chunking + BM25 para as políticas foi testada de verdade contra as
  perguntas de exemplo do desafio (incluindo "posso devolver meu pedido?")
  durante o desenvolvimento — a primeira versão falhava exatamente nesse
  caso (BM25 puro não achava "devolução" a partir de "devolver"), o que foi
  identificado rodando consultas reais contra o índice, não em teoria. Isso
  levou à adição do stemming leve, com um teste de regressão específico
  (`tests/test_policy_search.py`).
- **Escrita de código**: todo o código (`src/agent/`, `cli.py`, `tests/`) foi
  escrito pelo Claude Code; eu revisei a cada etapa (dados → políticas →
  ferramentas/prompt → loop do agente → CLI), rodando os testes e consultas
  manuais de verificação a cada módulo novo antes de seguir para o próximo,
  em vez de gerar o projeto inteiro de uma vez.
- **Geração dos exemplos de conversa**: na primeira versão do projeto (sobre
  a API da Anthropic), a conta usada para testes ficou sem crédito
  (`400 invalid_request_error: Your credit balance is too low`) bem no
  momento de gerar os exemplos finais — a API da Anthropic é paga desde a
  primeira chamada, sem tier gratuito. Diante disso, segui a orientação do
  próprio enunciado ("assuma uma interpretação razoável, documente a
  suposição e siga em frente") e escrevi as 5 conversas à mão, com os números
  vindos de saídas reais de `store_data.py`/`policy_search.py` (não
  inventados, só a redação do assistente não veio de uma chamada ao modelo) —
  documentado no topo de cada arquivo em `examples/` naquele momento. Depois
  da troca de provedor para o Gemini (ver "LLM e provedor"), com tier
  gratuito de verdade disponível, rodei `scripts/generate_examples.py` contra
  a API de verdade e substituí os 5 arquivos por transcrições reais — não há
  mais nenhum exemplo "escrito à mão" no repositório.
- **Troca de provedor Anthropic → Gemini**: pedida explicitamente numa
  mensagem separada, depois do projeto já funcionando. Antes de escrever
  qualquer código Gemini, pedi ao Claude Code para não confiar em memória
  de treinamento para a forma exata do SDK `google-genai` (nomes de classe,
  assinatura de métodos) — WebFetch nas docs oficiais trouxe uma resposta
  visivelmente desatualizada/inconsistente (mencionava uma "Interactions
  API" e um modelo `gemini-3.8-flash` que não bateu com o pacote real), então
  a fonte de verdade usada foi **introspecção do pacote `google-genai`
  realmente instalado no venv** (`inspect.signature`, `model_fields`,
  `inspect.getsource`) — mais lento que confiar num resumo de doc, mas
  elimina a alucinação de API. Isso também pegou, na prática e não só em
  teoria, que o modelo pedido inicialmente (`gemini-2.5-flash`) retorna 404
  para chaves novas, e que o substituto sugerido pela própria API
  (`gemini-3.6-flash`) tem cota gratuita baixa demais (20 requisições/dia)
  para o fluxo de trabalho deste projeto — o que só apareceu rodando
  chamadas reais contra a API, não checando documentação. Cada decisão dessas
  (qual modelo usar, como reagir ao erro 404, como reagir à cota) foi
  levantada como pergunta explícita antes de eu seguir em frente, em vez de
  escolhida silenciosamente. Antes de mexer em qualquer arquivo de config,
  também verifiquei o histórico do git inteiro (`git log --all -p`) atrás do
  valor de uma eventual chave de API da Anthropic vazada — só o placeholder
  `sk-ant-...` do `.env.example` apareceu; a chave real nunca foi commitada
  (`.env` sempre esteve fora do controle de versão).
- **Controle de versão**: os commits foram feitos incrementalmente ao longo
  do desenvolvimento (dados → camada de dados → busca de políticas →
  ferramentas/prompt/loop/CLI → exemplos → README), refletindo o progresso
  real da sessão, não um único commit squashed no final.
