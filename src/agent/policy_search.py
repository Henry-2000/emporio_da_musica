"""Recuperação de trechos do manual de políticas (data/politicas_da_loja.pdf).

Abordagem escolhida: "RAG leve" sem embeddings — o manual tem só 8 páginas e
10 seções numeradas, então dividir o texto por seção e buscar com BM25
(recuperação lexical, via rank-bm25) é suficiente para achar o trecho certo,
sem depender de uma API de embeddings ou de um banco vetorial. Ver README >
"Arquitetura de retrieval" para a justificativa completa e o trade-off.

O PDF extrai melhor com pypdf no modo `extraction_mode="layout"`: no modo
padrão, cada palavra vem em uma linha própria (o PDF foi gerado com uma
palavra por "célula" de texto); no modo layout o texto sai com quebras de
parágrafo e espaçamento de tabela preservados, o que permite dividir por
cabeçalho de seção com uma regex simples.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rank_bm25 import BM25Okapi

from . import config

# Cabeçalho/rodapé repetidos em toda página — não carregam informação.
_NOISE_LINE_PATTERNS = [
    re.compile(r"^Empório da Música Manual de Políticas e Procedimentos$"),
    re.compile(r"^Página\s+\d+$"),
    re.compile(r"^Documento interno.*$"),
]

# Título de seção de primeiro nível: "1. Sobre a Empório da Música", "10. Disposições Finais".
# Precisa começar na coluna 0 (sem indentação) para não casar com itens de lista
# numerados dentro do texto, como "    1.   Saudação: ..." na seção 7.2.
_SECTION_HEADING_RE = re.compile(r"^(\d{1,2})\.\s+([A-ZÀ-Ý].*)$", re.MULTILINE)


@dataclass(frozen=True)
class PolicyChunk:
    section_number: str
    title: str
    text: str

    @property
    def heading(self) -> str:
        return f"{self.section_number}. {self.title}"


def _extract_layout_text() -> str:
    from pypdf import PdfReader  # import local: só é necessário aqui

    reader = PdfReader(str(config.POLICY_PDF_PATH))
    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    return "\n".join(pages)


def _clean_body(raw_body: str) -> str:
    lines = []
    for line in raw_body.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p.match(line) for p in _NOISE_LINE_PATTERNS):
            continue
        # Normaliza marcadores de lista ("•") e espaçamento interno de tabelas.
        line = re.sub(r"^[•·]\s*", "- ", line)
        line = re.sub(r"\s{2,}", " ", line)
        lines.append(line)
    return "\n".join(lines).strip()


def _split_into_chunks(full_text: str) -> list[PolicyChunk]:
    matches = list(_SECTION_HEADING_RE.finditer(full_text))
    chunks = []
    for i, m in enumerate(matches):
        number, title = m.group(1), m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = _clean_body(full_text[start:end])
        chunks.append(PolicyChunk(section_number=number, title=title, text=body))
    return chunks


def _normalize(text: str) -> str:
    """Minúsculas e sem acentos, para tornar a busca robusta a variações
    como 'endereco' vs 'endereço'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _stem(token: str) -> str:
    """Poor-man's stemming: corta o token nos primeiros 5 caracteres.

    O BM25 é uma busca lexical exata — sem isso, "devolver" (na pergunta do
    cliente) nunca casaria com "devolução" (no texto do manual), porque são
    tokens diferentes. Cortar para um prefixo comum recupera a maior parte
    dessas variações de gênero/número/conjugação em português sem precisar
    de um stemmer completo (ex.: NLTK RSLP) só para um documento de 8 páginas.
    Tokens curtos (artigos, preposições) ficam como estão.
    """
    return token[:5] if len(token) >= 6 else token


def _tokenize(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", _normalize(text))]


class _PolicyIndex:
    """Índice BM25 preguiçoso (construído na primeira busca)."""

    def __init__(self) -> None:
        self._chunks: list[PolicyChunk] | None = None
        self._bm25: BM25Okapi | None = None

    def _ensure_built(self) -> None:
        if self._chunks is not None:
            return
        full_text = _extract_layout_text()
        self._chunks = _split_into_chunks(full_text)
        corpus = [_tokenize(f"{c.title} {c.text}") for c in self._chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 2) -> list[tuple[PolicyChunk, float]]:
        self._ensure_built()
        assert self._chunks is not None and self._bm25 is not None
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._chunks, scores), key=lambda pair: pair[1], reverse=True)
        # Só devolve trechos com alguma relevância real — score 0 significa
        # nenhuma palavra da pergunta apareceu na seção.
        return [(chunk, score) for chunk, score in ranked[:top_k] if score > 0]

    def all_chunks(self) -> list[PolicyChunk]:
        self._ensure_built()
        assert self._chunks is not None
        return self._chunks


_index = _PolicyIndex()


def search_policies(query: str, top_k: int = 2) -> list[dict[str, str]]:
    """Retorna as até `top_k` seções do manual mais relevantes para `query`.

    Cada item tem `heading` (ex.: "4. Política de Trocas e Devoluções") e
    `text` (o corpo limpo da seção). Lista vazia significa que nada no
    manual bateu com a pergunta — o chamador deve tratar isso como "não sei"
    em vez de inventar uma política.
    """
    results = _index.search(query, top_k=top_k)
    return [{"heading": chunk.heading, "text": chunk.text} for chunk, _score in results]
