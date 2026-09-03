"""Definições de ferramentas (function calling) expostas ao modelo.

Cada ferramenta é uma consulta parametrizada e previsível sobre os dados da
loja (store_data.py) ou sobre o manual de políticas (policy_search.py) — não
há uma ferramenta de "SQL livre" ou "pergunte qualquer coisa ao PDF"; ver a
justificativa em store_data.py e no README > "Por que não um agente de SQL".
"""

from __future__ import annotations

from typing import Any

from . import policy_search, store_data

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_products",
        "description": (
            "Busca produtos no catálogo da loja por texto livre, categoria e/ou faixa de "
            "preço. Use para perguntas como 'quais violões vocês têm até R$1000?' ou "
            "'tem teclado da Yamaha?'. Categorias existentes: Guitarras, Baixos, "
            "Baterias e Percussão, Teclados e Pianos, Violões, Instrumentos de Sopro "
            "(Madeiras), Instrumentos de Sopro (Metais), Cordas Orquestrais, Ukuleles. "
            "Não use para acessórios (cordas, cabos, palhetas, pedais, amplificadores, "
            "cases) — a loja não vende esse tipo de item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Termo livre a buscar no nome/descrição do produto (opcional).",
                },
                "category": {
                    "type": "string",
                    "description": "Nome (ou parte do nome) da categoria, ex.: 'violões' (opcional).",
                },
                "min_price": {
                    "type": "number",
                    "description": "Preço mínimo em reais (opcional).",
                },
                "max_price": {
                    "type": "number",
                    "description": "Preço máximo em reais (opcional).",
                },
                "only_available": {
                    "type": "boolean",
                    "description": (
                        "Se true, retorna só produtos ativos e com estoque > 0. "
                        "Use false (padrão) quando quiser saber se um produto existe "
                        "mesmo que esteja esgotado ou descontinuado, para poder explicar "
                        "a situação ao cliente."
                    ),
                },
            },
        },
    },
    {
        "name": "get_product_by_name",
        "description": (
            "Busca o(s) produto(s) cujo nome contenha o termo informado — use para "
            "perguntas de preço/disponibilidade sobre um modelo específico, ex.: "
            "'quanto custa o Takamine GD20?'. Pode retornar mais de um resultado se o "
            "termo for ambíguo (ex.: 'Yamaha'); nesse caso, peça ao cliente para "
            "especificar o modelo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nome (completo ou parcial) do produto.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_active_promotions",
        "description": (
            "Lista as promoções atualmente ativas no sistema, com o preço promocional já "
            "calculado. Use antes de confirmar qualquer desconto a um cliente — nunca "
            "afirme que uma promoção está valendo sem checar aqui primeiro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filtra promoções por categoria de produto (opcional).",
                },
            },
        },
    },
    {
        "name": "get_order_status",
        "description": (
            "Consulta o status de um ou mais pedidos por número do pedido, código de "
            "rastreio ou nome do cliente. Prefira sempre pedir o número do pedido ao "
            "cliente; se ele só souber o nome, use customer_name e, se houver mais de um "
            "pedido, peça para ele confirmar qual deles (não descreva os outros pedidos "
            "em detalhe)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "integer",
                    "description": "Número do pedido (opcional).",
                },
                "tracking_code": {
                    "type": "string",
                    "description": "Código de rastreio informado pelo cliente (opcional).",
                },
                "customer_name": {
                    "type": "string",
                    "description": "Nome do cliente, usado apenas se ele não souber o número do pedido (opcional).",
                },
            },
        },
    },
    {
        "name": "search_policies",
        "description": (
            "Busca no manual interno de políticas da loja (horário de funcionamento, "
            "formas de pagamento, trocas e devoluções, frete e entregas, promoções, "
            "garantia, privacidade, endereço/contato da loja). Use para qualquer pergunta "
            "sobre regras, procedimentos ou informações institucionais da loja — não para "
            "preço/estoque de produto ou status de pedido, que vêm de outras ferramentas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A pergunta ou tópico do cliente, em linguagem natural.",
                },
            },
            "required": ["query"],
        },
    },
]


def execute_tool(name: str, tool_input: dict[str, Any]) -> Any:
    """Despacha uma chamada de ferramenta para a função correspondente."""
    if name == "search_products":
        return store_data.search_products(
            query=tool_input.get("query"),
            category=tool_input.get("category"),
            min_price=tool_input.get("min_price"),
            max_price=tool_input.get("max_price"),
            only_available=tool_input.get("only_available", False),
        )
    if name == "get_product_by_name":
        return store_data.get_product_by_name(tool_input["name"])
    if name == "get_active_promotions":
        return store_data.get_active_promotions(category=tool_input.get("category"))
    if name == "get_order_status":
        return store_data.get_order_status(
            order_id=tool_input.get("order_id"),
            tracking_code=tool_input.get("tracking_code"),
            customer_name=tool_input.get("customer_name"),
        )
    if name == "search_policies":
        return policy_search.search_policies(tool_input["query"])

    raise ValueError(f"Ferramenta desconhecida: {name}")
