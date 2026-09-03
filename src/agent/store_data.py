"""Camada de dados estruturados (produtos, pedidos, clientes, promoções).

Carrega os CSVs fornecidos para um banco SQLite em memória, faz uma limpeza
leve (tipos numéricos, espaços em branco, normalização de status) e expõe
funções de consulta de alto nível que as ferramentas do agente (tools.py)
chamam diretamente. Preferimos SQLite a manter tudo em pandas porque:

- as consultas que o agente precisa (filtrar por categoria/preço, buscar por
  nome, achar pedido por id) mapeiam bem para SQL simples e parametrizado;
- fica fácil oferecer múltiplas funções de busca sem reimplementar filtros
  manualmente em pandas;
- o banco é reconstruído do zero a cada execução do processo (os CSVs são a
  fonte da verdade), então não há necessidade de um arquivo .db persistente.

Não expomos uma ferramenta de "SQL livre" para o modelo: cada função abaixo
é uma consulta parametrizada e previsível. Isso evita que o agente monte SQL
arbitrário (risco de erro/alucinação de coluna) — ver README > Limitações.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config

_SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER,
    price_brl REAL NOT NULL,
    description TEXT,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    specs TEXT,
    created_at TEXT
);

CREATE TABLE promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER,
    discount_percent REAL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT,
    phone TEXT,
    email TEXT,
    city TEXT
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TEXT,
    status TEXT,
    total_brl REAL,
    payment_method TEXT,
    tracking_code TEXT,
    estimated_delivery TEXT,
    notes TEXT
);

CREATE TABLE order_items (
    order_id INTEGER,
    quantity INTEGER,
    product_id INTEGER
);
"""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _clean_str(value: str | None) -> str | None:
    """Remove espaços nas pontas; converte string vazia em NULL."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_float(value: str | None) -> float | None:
    value = _clean_str(value)
    return float(value) if value is not None else None


def _to_int(value: str | None, default: int = 0) -> int:
    value = _clean_str(value)
    return int(float(value)) if value is not None else default


def _build_database() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)

    for row in _read_csv(config.CSV_FILES["categories"]):
        conn.execute(
            "INSERT INTO categories VALUES (?, ?, ?)",
            (
                _to_int(row["category_id"]),
                _clean_str(row["name"]),
                _clean_str(row["description"]),
            ),
        )

    for row in _read_csv(config.CSV_FILES["products"]):
        # specs vem como uma string JSON (ex.: {"top":"Spruce", ...}).
        # Mantemos como texto e só decodificamos quando formos exibir.
        conn.execute(
            "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _to_int(row["product_id"]),
                _clean_str(row["name"]),
                _to_int(row["category_id"]) if _clean_str(row["category_id"]) else None,
                _to_float(row["price_brl"]) or 0.0,
                _clean_str(row["description"]),
                _to_int(row["stock_quantity"], default=0),
                (_clean_str(row["status"]) or "active").lower(),
                _clean_str(row["specs"]),
                _clean_str(row["created_at"]),
            ),
        )

    for row in _read_csv(config.CSV_FILES["promotions"]):
        conn.execute(
            "INSERT INTO promotions VALUES (?, ?, ?, ?, ?)",
            (
                _to_int(row["promotion_id"]),
                _to_int(row["product_id"]) if _clean_str(row["product_id"]) else None,
                _to_float(row["discount_percent"]) or 0.0,
                _clean_str(row["description"]),
                _to_int(row["is_active"], default=0),
            ),
        )

    for row in _read_csv(config.CSV_FILES["customers"]):
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
            (
                _to_int(row["customer_id"]),
                _clean_str(row["name"]),
                _clean_str(row["phone"]),
                _clean_str(row["email"]),
                _clean_str(row["city"]),
            ),
        )

    for row in _read_csv(config.CSV_FILES["orders"]):
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _to_int(row["order_id"]),
                _to_int(row["customer_id"]) if _clean_str(row["customer_id"]) else None,
                _clean_str(row["order_date"]),
                (_clean_str(row["status"]) or "unknown").lower(),
                _to_float(row["total_brl"]) or 0.0,
                _clean_str(row["payment_method"]),
                _clean_str(row["tracking_code"]),
                _clean_str(row["estimated_delivery"]),
                _clean_str(row["notes"]),
            ),
        )

    for row in _read_csv(config.CSV_FILES["order_items"]):
        conn.execute(
            "INSERT INTO order_items VALUES (?, ?, ?)",
            (
                _to_int(row["order_id"]),
                _to_int(row["quantity"], default=1),
                _to_int(row["product_id"]),
            ),
        )

    conn.commit()
    return conn


class _Store:
    """Wrapper preguiçoso (lazy) em torno da conexão SQLite em memória."""

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = _build_database()
        return self._conn


_store = _Store()


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def _attach_promotion(product: dict[str, Any]) -> dict[str, Any]:
    """Adiciona informação de promoção ativa (se houver) e preço com desconto."""
    conn = _store.conn
    promo = conn.execute(
        """
        SELECT discount_percent, description
        FROM promotions
        WHERE product_id = ? AND is_active = 1
        ORDER BY discount_percent DESC
        LIMIT 1
        """,
        (product["product_id"],),
    ).fetchone()

    product["active_promotion"] = None
    product["price_with_promotion_brl"] = None
    if promo is not None:
        discount = promo["discount_percent"]
        discounted = round(product["price_brl"] * (1 - discount / 100), 2)
        product["active_promotion"] = {
            "discount_percent": discount,
            "description": promo["description"],
        }
        product["price_with_promotion_brl"] = discounted
    return product


def search_products(
    query: str | None = None,
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    only_available: bool = False,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Busca produtos por texto livre, categoria e/ou faixa de preço.

    `query` casa (case-insensitive) com nome ou descrição do produto.
    `category` casa (case-insensitive, parcial) com o nome da categoria.
    `only_available` filtra para status='active' e estoque > 0.
    Produtos 'discontinued' e 'coming_soon' são incluídos por padrão para que
    o agente possa explicar a situação ao cliente em vez de simplesmente
    omitir o produto.
    """
    conn = _store.conn
    clauses = []
    params: list[Any] = []

    if query:
        clauses.append("(LOWER(p.name) LIKE ? OR LOWER(p.description) LIKE ?)")
        like = f"%{query.lower()}%"
        params.extend([like, like])

    if category:
        clauses.append("LOWER(c.name) LIKE ?")
        params.append(f"%{category.lower()}%")

    if min_price is not None:
        clauses.append("p.price_brl >= ?")
        params.append(min_price)

    if max_price is not None:
        clauses.append("p.price_brl <= ?")
        params.append(max_price)

    if only_available:
        clauses.append("p.status = 'active' AND p.stock_quantity > 0")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT p.*, c.name AS category_name
        FROM products p
        LEFT JOIN categories c ON c.category_id = p.category_id
        {where}
        ORDER BY p.price_brl ASC
        LIMIT ?
    """
    params.append(limit)
    rows = _rows_to_dicts(conn.execute(sql, params).fetchall())
    return [_attach_promotion(r) for r in rows]


def get_product_by_name(name: str) -> list[dict[str, Any]]:
    """Busca produto(s) cujo nome contenha o termo informado.

    Retorna uma lista porque o termo pode casar com mais de um produto
    (ex.: "Yamaha" retorna vários modelos); o chamador decide como desambiguar.
    """
    conn = _store.conn
    rows = _rows_to_dicts(
        conn.execute(
            """
            SELECT p.*, c.name AS category_name
            FROM products p
            LEFT JOIN categories c ON c.category_id = p.category_id
            WHERE LOWER(p.name) LIKE ?
            ORDER BY p.price_brl ASC
            LIMIT 10
            """,
            (f"%{name.lower()}%",),
        ).fetchall()
    )
    return [_attach_promotion(r) for r in rows]


def get_active_promotions(category: str | None = None) -> list[dict[str, Any]]:
    """Lista promoções atualmente ativas, com o produto associado."""
    conn = _store.conn
    clauses = ["pr.is_active = 1"]
    params: list[Any] = []
    if category:
        clauses.append("LOWER(c.name) LIKE ?")
        params.append(f"%{category.lower()}%")

    sql = f"""
        SELECT pr.promotion_id, pr.discount_percent, pr.description AS promo_description,
               p.product_id, p.name AS product_name, p.price_brl, c.name AS category_name
        FROM promotions pr
        JOIN products p ON p.product_id = pr.product_id
        LEFT JOIN categories c ON c.category_id = p.category_id
        WHERE {' AND '.join(clauses)}
        ORDER BY pr.discount_percent DESC
    """
    rows = _rows_to_dicts(conn.execute(sql, params).fetchall())
    for r in rows:
        r["price_with_promotion_brl"] = round(
            r["price_brl"] * (1 - r["discount_percent"] / 100), 2
        )
    return rows


def get_order_status(
    order_id: int | None = None,
    tracking_code: str | None = None,
    customer_name: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta pedido(s) por número do pedido, código de rastreio ou nome do cliente.

    Retorna uma lista de pedidos (cada um já com seus itens) porque uma busca
    por nome de cliente pode casar com mais de um pedido — o agente deve
    então pedir o número do pedido para confirmar, em vez de expor todos os
    detalhes de primeira (ver README > Limitações, sobre autenticação).
    """
    conn = _store.conn
    clauses = []
    params: list[Any] = []

    if order_id is not None:
        clauses.append("o.order_id = ?")
        params.append(order_id)
    if tracking_code:
        clauses.append("LOWER(o.tracking_code) = ?")
        params.append(tracking_code.lower())
    if customer_name:
        clauses.append("LOWER(cu.name) LIKE ?")
        params.append(f"%{customer_name.lower()}%")

    if not clauses:
        return []

    sql = f"""
        SELECT o.*, cu.name AS customer_name
        FROM orders o
        LEFT JOIN customers cu ON cu.customer_id = o.customer_id
        WHERE {' AND '.join(clauses)}
        ORDER BY o.order_date DESC
        LIMIT 10
    """
    orders = _rows_to_dicts(conn.execute(sql, params).fetchall())

    for order in orders:
        items = conn.execute(
            """
            SELECT oi.quantity, p.name AS product_name, p.price_brl
            FROM order_items oi
            JOIN products p ON p.product_id = oi.product_id
            WHERE oi.order_id = ?
            """,
            (order["order_id"],),
        ).fetchall()
        order["items"] = _rows_to_dicts(items)

    return orders


def parse_specs(specs_json: str | None) -> dict[str, Any]:
    if not specs_json:
        return {}
    try:
        return json.loads(specs_json)
    except json.JSONDecodeError:
        return {}
