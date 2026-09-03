#!/usr/bin/env python
"""Gera os arquivos de exemplo em examples/ rodando o agente de verdade
contra a API do Gemini (não são conversas inventadas).

Uso:
    python scripts/generate_examples.py

Requer GEMINI_API_KEY configurada (.env ou variável de ambiente).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agent.config import MODEL_NAME  # noqa: E402
from agent.core import ConversationAgent  # noqa: E402

EXAMPLES_DIR = ROOT / "examples"

SCENARIOS = [
    {
        "filename": "01_busca_por_categoria_e_preco.md",
        "title": "Busca no catálogo por categoria e faixa de preço",
        "note": "Consulta ao catálogo de produtos (search_products / get_product_by_name).",
        "messages": [
            "Oi! quais violões vocês têm até R$1000?",
            "o Tagima Woodstock tem quantas unidades no estoque?",
        ],
    },
    {
        "filename": "02_horario_e_endereco.md",
        "title": "Informações gerais da loja",
        "note": "Consulta às políticas da loja (search_policies).",
        "messages": [
            "Qual o endereço da loja?",
            "e vocês abrem aos domingos?",
        ],
    },
    {
        "filename": "03_preco_produto_especifico.md",
        "title": "Consulta de preço de um produto específico",
        "note": "Consulta ao catálogo de produtos (get_product_by_name).",
        "messages": [
            "Quanto custa o Takamine GD20?",
            "e o GC5CE, qual a diferença de preço pro GD20?",
        ],
    },
    {
        "filename": "04_devolucao_e_status_pedido.md",
        "title": "Devolução aplicada a um pedido real (cenário não trivial)",
        "note": (
            "Combina política de devolução (search_policies) com consulta de "
            "um pedido real (get_order_status) e raciocínio sobre prazo a "
            "partir da data do pedido — o pedido 4 foi entregue em "
            "10/12/2025, bem fora da janela de 7 dias de arrependimento."
        ),
        "messages": [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "é o pedido número 4",
        ],
    },
    {
        "filename": "05_fora_de_escopo.md",
        "title": "Perguntas fora do escopo da loja",
        "note": "Acessório que a loja não vende, e uma pergunta sem nenhuma relação com a loja.",
        "messages": [
            "Vocês vendem cordas para violão?",
            "você pode resolver uma equação de segundo grau pra mim? x^2 - 5x + 6 = 0",
        ],
    },
]


def run_scenario(scenario: dict) -> str:
    agent = ConversationAgent()
    lines = [
        f"# {scenario['title']}",
        "",
        f"_{scenario['note']}_",
        "",
        f"Modelo: `{MODEL_NAME}` · Gerado rodando `cli.py` de ponta a ponta contra a API do Gemini.",
        "",
        "---",
        "",
    ]
    for user_text in scenario["messages"]:
        # ConversationAgent já faz retry com backoff para erros transitórios
        # (503 de alta demanda, 429/5xx) — ver ConversationAgent.__init__.
        reply = agent.send(user_text)
        lines.append(f"**Cliente:** {user_text}")
        lines.append("")
        lines.append(f"**Empório da Música:** {reply}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    EXAMPLES_DIR.mkdir(exist_ok=True)
    for scenario in SCENARIOS:
        print(f"Gerando {scenario['filename']}...")
        content = run_scenario(scenario)
        path = EXAMPLES_DIR / scenario["filename"]
        path.write_text(content, encoding="utf-8")
        print(f"  -> salvo em {path}")


if __name__ == "__main__":
    main()
