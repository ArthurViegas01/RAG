"""
Testes unitarios para as funcoes utilitarias do search_service.

Funcoes puras — sem banco, sem embedding, sem nenhuma dependencia externa.
"""
from __future__ import annotations

import app.services.search_service  # pre-import so patch paths resolve

import pytest

from app.services.search_service import (
    SearchResult,
    _expand_query,
    _expand_range,
    _extract_keywords,
    _remove_accents,
    _rrf_score,
)
from app.services.search_service import SearchService


# ── _rrf_score ────────────────────────────────────────────────────────────────

class TestRrfScore:
    def test_rank_0_default_k(self):
        assert _rrf_score(0) == pytest.approx(1 / 60)

    def test_rank_60_default_k(self):
        assert _rrf_score(60) == pytest.approx(1 / 120)

    def test_custom_k(self):
        assert _rrf_score(0, k=10) == pytest.approx(1 / 10)

    def test_higher_rank_lower_score(self):
        assert _rrf_score(0) > _rrf_score(10) > _rrf_score(100)

    def test_score_is_positive(self):
        assert _rrf_score(999) > 0


# ── _remove_accents ───────────────────────────────────────────────────────────

class TestRemoveAccents:
    def test_removes_tilde_a(self):
        assert _remove_accents("ação") == "acao"

    def test_removes_acute_a(self):
        assert _remove_accents("fácil") == "facil"

    def test_removes_cedilla(self):
        assert _remove_accents("coração") == "coracao"

    def test_removes_acute_e(self):
        assert _remove_accents("café") == "cafe"

    def test_removes_circumflex_e(self):
        assert _remove_accents("você") == "voce"

    def test_removes_acute_i(self):
        assert _remove_accents("índice") == "indice"

    def test_removes_acute_o(self):
        assert _remove_accents("nós") == "nos"

    def test_removes_acute_u(self):
        assert _remove_accents("único") == "unico"

    def test_plain_ascii_unchanged(self):
        assert _remove_accents("hello world") == "hello world"

    def test_uppercase_accents(self):
        result = _remove_accents("AÇÃO")
        assert result == "ACAO"

    def test_mixed_case(self):
        result = _remove_accents("Ação Rápida")
        assert "a" in result.lower() and "c" in result.lower()


# ── _expand_range ─────────────────────────────────────────────────────────────

class TestExpandRange:
    def test_primeiras_n_leis(self):
        result = _expand_range("primeiras 3 leis")
        assert "lei 1" in result
        assert "lei 2" in result
        assert "lei 3" in result

    def test_primeiros_n_artigos(self):
        result = _expand_range("primeiros 2 artigos")
        assert "artigo 1" in result
        assert "artigo 2" in result

    def test_primeiros_n_capitulos(self):
        result = _expand_range("primeiros 4 capitulos")
        assert "capitulo 1" in result
        assert "capitulo 4" in result

    def test_n_primeiras_leis(self):
        result = _expand_range("3 primeiras leis")
        assert "lei 1" in result
        assert "lei 3" in result

    def test_no_match_returns_empty(self):
        assert _expand_range("machine learning") == []

    def test_caps_at_15_items(self):
        result = _expand_range("primeiras 20 leis")
        assert len(result) <= 15

    def test_accented_input_normalized(self):
        result = _expand_range("primeiras 2 leis")
        assert len(result) == 2


# ── _expand_query ─────────────────────────────────────────────────────────────

class TestExpandQuery:
    def test_returns_list(self):
        assert isinstance(_expand_query("machine learning"), list)

    def test_original_query_in_result(self):
        assert "machine learning" in _expand_query("machine learning")

    def test_ordinal_expanded(self):
        result = _expand_query("primeira lei")
        assert "1" in result

    def test_isolated_numbers_extracted(self):
        result = _expand_query("artigo 32")
        assert "32" in result

    def test_no_duplicates(self):
        result = _expand_query("primeira primeira")
        assert len(result) == len(set(result))

    def test_empty_string(self):
        result = _expand_query("")
        assert isinstance(result, list)

    def test_range_expansion_included(self):
        result = _expand_query("primeiras 3 leis")
        assert "lei 1" in result
        assert "lei 3" in result


# ── _extract_keywords ─────────────────────────────────────────────────────────

class TestExtractKeywords:
    def test_returns_list(self):
        assert isinstance(_extract_keywords("machine learning"), list)

    def test_removes_stopwords(self):
        kws = _extract_keywords("o que e machine learning")
        assert "o" not in kws
        assert "que" not in kws
        assert "e" not in kws

    def test_keeps_meaningful_words(self):
        kws = _extract_keywords("machine learning inteligencia artificial")
        assert "machine" in kws
        assert "learning" in kws

    def test_no_duplicates(self):
        kws = _extract_keywords("lei lei lei")
        assert len(kws) == len(set(kws))

    def test_numbers_kept(self):
        kws = _extract_keywords("artigo 32")
        assert "32" in kws

    def test_empty_query(self):
        assert isinstance(_extract_keywords(""), list)

    def test_only_stopwords_returns_empty_or_minimal(self):
        kws = _extract_keywords("o a de")
        # All are stopwords — result should be empty
        for kw in kws:
            assert kw not in {"o", "a", "de"}


# ── SearchService._fuse_rrf ───────────────────────────────────────────────────

def _make_result(chunk_id, similarity=0.8, match_type="semantic"):
    from unittest.mock import MagicMock
    from uuid import uuid4
    r = MagicMock()
    r.chunk_id = chunk_id
    r.document_id = uuid4()
    r.content = "conteudo"
    r.chunk_index = 0
    r.similarity = similarity
    r.match_type = match_type
    r.document_filename = None
    return r


class TestFuseRrf:
    def test_empty_inputs_return_empty(self):
        assert SearchService._fuse_rrf([], [], top_k=5) == []

    def test_semantic_only(self):
        results = [_make_result(i) for i in range(3)]
        fused = SearchService._fuse_rrf(results, [], top_k=5)
        assert len(fused) == 3

    def test_keyword_only(self):
        results = [_make_result(i, match_type="keyword") for i in range(3)]
        fused = SearchService._fuse_rrf([], results, top_k=5)
        assert len(fused) == 3

    def test_top_k_respected(self):
        semantic = [_make_result(i) for i in range(10)]
        fused = SearchService._fuse_rrf(semantic, [], top_k=3)
        assert len(fused) == 3

    def test_shared_chunk_becomes_hybrid(self):
        chunk_id = 42
        sem = [_make_result(chunk_id, match_type="semantic")]
        kw = [_make_result(chunk_id, match_type="keyword")]
        fused = SearchService._fuse_rrf(sem, kw, top_k=5)
        assert len(fused) == 1
        assert fused[0].match_type == "hybrid"

    def test_earlier_rank_scores_higher(self):
        # rank 0 scores higher than rank 5
        sem = [_make_result(i) for i in range(6)]
        fused = SearchService._fuse_rrf(sem, [], top_k=6)
        scores = [r.similarity for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_combined_score_higher_than_single(self):
        """Chunk em ambas as listas deve ficar na frente."""
        shared_id = 99
        unique_id = 100
        sem = [_make_result(shared_id), _make_result(unique_id)]
        kw = [_make_result(shared_id)]
        fused = SearchService._fuse_rrf(sem, kw, top_k=5)
        ids = [r.chunk_id for r in fused]
        assert ids[0] == shared_id
