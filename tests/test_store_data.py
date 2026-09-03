"""Testes leves da camada de dados (store_data.py).

Cobrem os casos usados diretamente pelos exemplos de conversa do desafio:
busca de violões por preço, preço de um produto específico e status de
pedido. Não é uma suíte exaustiva — o objetivo é garantir que a limpeza de
dados e as consultas usadas pelas ferramentas do agente continuam corretas
se os CSVs mudarem.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent import store_data as sd  # noqa: E402


class TestSearchProducts(unittest.TestCase):
    def test_violoes_ate_1000_sao_todos_da_categoria_e_dentro_do_preco(self):
        results = sd.search_products(category="violões", max_price=1000)
        self.assertGreater(len(results), 0)
        for p in results:
            self.assertEqual(p["category_name"], "Violões")
            self.assertLessEqual(p["price_brl"], 1000)

    def test_busca_por_texto_casa_no_nome(self):
        results = sd.search_products(query="takamine")
        self.assertTrue(any("Takamine" in p["name"] for p in results))

    def test_only_available_exclui_sem_estoque_e_descontinuados(self):
        results = sd.search_products(only_available=True, limit=1000)
        for p in results:
            self.assertEqual(p["status"], "active")
            self.assertGreater(p["stock_quantity"], 0)


class TestGetProductByName(unittest.TestCase):
    def test_takamine_gd20_tem_preco_correto(self):
        results = sd.get_product_by_name("Takamine GD20")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["price_brl"], 2199.0)

    def test_termo_ambiguo_retorna_varios_produtos(self):
        results = sd.get_product_by_name("Yamaha")
        self.assertGreater(len(results), 1)


class TestOrderStatus(unittest.TestCase):
    def test_busca_por_order_id_retorna_itens_do_pedido(self):
        orders = sd.get_order_status(order_id=1)
        self.assertEqual(len(orders), 1)
        order = orders[0]
        self.assertEqual(order["status"], "delivered")
        self.assertGreater(len(order["items"]), 0)

    def test_order_id_inexistente_retorna_lista_vazia(self):
        self.assertEqual(sd.get_order_status(order_id=999999), [])

    def test_sem_nenhum_filtro_retorna_lista_vazia(self):
        # Evita devolver o banco de pedidos inteiro por engano.
        self.assertEqual(sd.get_order_status(), [])


class TestPromotions(unittest.TestCase):
    def test_promocoes_ativas_tem_preco_com_desconto_menor_que_preco_cheio(self):
        promos = sd.get_active_promotions()
        self.assertGreater(len(promos), 0)
        for promo in promos:
            self.assertLess(promo["price_with_promotion_brl"], promo["price_brl"])


if __name__ == "__main__":
    unittest.main()
