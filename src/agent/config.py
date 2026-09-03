"""Configuração central do agente: caminhos, modelo e chave de API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega variáveis de um arquivo .env na raiz do projeto, se existir.
load_dotenv()

# Raiz do projeto = dois níveis acima deste arquivo (src/agent/config.py -> raiz/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

POLICY_PDF_PATH = DATA_DIR / "politicas_da_loja.pdf"

CSV_FILES = {
    "categories": DATA_DIR / "categories.csv",
    "customers": DATA_DIR / "customers.csv",
    "orders": DATA_DIR / "orders.csv",
    "order_items": DATA_DIR / "order_items.csv",
    "products": DATA_DIR / "products.csv",
    "promotions": DATA_DIR / "promotions.csv",
}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Modelo principal do agente. `gemini-2.5-flash` (a escolha original) retorna
# 404 para chaves novas ("no longer available to new users"); o substituto
# que a própria API recomenda, `gemini-3.6-flash`, funciona mas tem cota
# gratuita de só 20 requisições/dia — não sobrevive nem a uma sessão de teste.
# `gemini-3.5-flash-lite` (nível "lite") funcionou sem esbarrar em cota
# durante o desenvolvimento — ver README > "Decisões técnicas" para o
# histórico completo dessa descoberta e a justificativa.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

MAX_TOKENS = 2048

# Trava de segurança para o loop de tool-use: número máximo de idas e vindas
# de ferramenta dentro de uma única mensagem do usuário, para nunca travar
# em loop caso o modelo insista em chamar ferramentas indefinidamente.
MAX_TOOL_ITERATIONS = 6

# Quantos turnos de histórico (pares usuário/assistente) manter no contexto
# enviado ao modelo. Evita custo/latência crescendo sem limite em sessões longas.
MAX_HISTORY_TURNS = 20
