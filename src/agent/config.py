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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Modelo principal do agente. Sonnet equilibra qualidade e custo para um
# fluxo conversacional com várias chamadas de ferramenta por interação.
# Ver README > "Decisões técnicas" para a justificativa completa.
MODEL_NAME = os.environ.get("EMPORIO_MODEL", "claude-sonnet-5")

MAX_TOKENS = 1024

# Quantos turnos de histórico (pares usuário/assistente) manter no contexto
# enviado ao modelo. Evita custo/latência crescendo sem limite em sessões longas.
MAX_HISTORY_TURNS = 20
