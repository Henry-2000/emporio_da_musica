"""Testes da recuperação de políticas (policy_search.py).

Cobrem o caso mais crítico do desafio: a pergunta "posso devolver meu
pedido?" tem que trazer a seção de Trocas e Devoluções mesmo sem repetir as
palavras exatas do manual (o cliente diz "devolver", o manual diz
"devolução") — daí o teste do stemming leve em `_tokenize`.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent import policy_search as ps  # noqa: E402


class TestSearchPolicies(unittest.TestCase):
    def test_devolucao_encontra_secao_de_trocas_mesmo_sem_repetir_a_palavra(self):
        results = ps.search_policies("posso devolver meu pedido?")
        self.assertTrue(results)
        self.assertEqual(results[0]["heading"], "4. Política de Trocas e Devoluções")

    def test_endereco_encontra_secao_sobre_a_loja(self):
        results = ps.search_policies("qual o endereço da loja")
        self.assertTrue(results)
        self.assertEqual(results[0]["heading"], "1. Sobre a Empório da Música")

    def test_horario_encontra_secao_de_horario(self):
        results = ps.search_policies("horário de funcionamento")
        self.assertTrue(results)
        self.assertEqual(results[0]["heading"], "2. Horário de Funcionamento")

    def test_manual_tem_dez_secoes_de_primeiro_nivel(self):
        chunks = ps._index.all_chunks()
        self.assertEqual(len(chunks), 10)
        self.assertEqual(chunks[0].section_number, "1")
        self.assertEqual(chunks[-1].section_number, "10")


class TestStemming(unittest.TestCase):
    def test_variacoes_de_genero_numero_convergem_para_o_mesmo_stem(self):
        self.assertEqual(ps._stem("devolver"), ps._stem("devolucao"))
        self.assertEqual(ps._stem("pedido"), ps._stem("pedidos"))


if __name__ == "__main__":
    unittest.main()
