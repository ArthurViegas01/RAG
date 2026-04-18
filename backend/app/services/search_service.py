"""
Servico de busca hibrida: semantica (pgvector) + keyword (PostgreSQL full-text).
"""

import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Document
from app.services.embedding_service import get_embedding_service


class SearchResult:
    """Resultado de uma busca (semantica ou hibrida)."""

    def __init__(self, chunk, similarity: float, match_type: str = "semantic"):
        self.chunk_id = chunk.id
        self.document_id = chunk.document_id
        self.content = chunk.content
        self.chunk_index = chunk.chunk_index
        self.similarity = similarity
        self.match_type = match_type
        self.document_filename = None


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


_ORDINAL_MAP = {
    # singular
    "primeira": "1",  "primeiro": "1",
    "segunda":  "2",  "segundo":  "2",
    "terceira": "3",  "terceiro": "3",
    "quarta":   "4",  "quarto":   "4",
    "quinta":   "5",  "quinto":   "5",
    "sexta":    "6",  "sexto":    "6",
    "setima":   "7",  "setimo":   "7",
    "oitava":   "8",  "oitavo":   "8",
    "nona":     "9",  "nono":     "9",
    "decima":   "10", "decimo":   "10",
    "vigesima": "20", "vigesimo": "20",
    "trigesima":"30", "trigesimo":"30",
    "quadragesima":"40","quadragesimo":"40",
    # plural (ex: "primeiras 3 leis")
    "primeiras": "1", "primeiros": "1",
    "segundas":  "2", "segundos":  "2",
    "terceiras": "3", "terceiros": "3",
    "quartas":   "4", "quartos":   "4",
    "quintas":   "5", "quintos":   "5",
    "sextas":    "6", "sextos":    "6",
    "oitavas":   "8", "oitavos":   "8",
    "nonas":     "9", "nonos":     "9",
}


def _remove_accents(text: str) -> str:
    for a, b in [("a","a"),("a","a"),("a","a"),("a","a"),
                 ("e","e"),("e","e"),("i","i"),("o","o"),
                 ("o","o"),("u","u"),("c","c")]:
        pass
    for src, dst in [
        ("\u00e3","a"), ("\u00e1","a"), ("\u00e2","a"), ("\u00e0","a"),
        ("\u00e9","e"), ("\u00ea","e"), ("\u00ed","i"),
        ("\u00f3","o"), ("\u00f4","o"), ("\u00fa","u"), ("\u00e7","c"),
        ("\u00c3","A"), ("\u00c1","A"), ("\u00c2","A"),
        ("\u00c9","E"), ("\u00ca","E"), ("\u00cd","I"),
        ("\u00d3","O"), ("\u00d4","O"), ("\u00da","U"), ("\u00c7","C"),
    ]:
        text = text.replace(src, dst)
    return text


def _expand_range(query: str) -> list:
    """
    "primeiras 3 leis" -> ["lei 1", "lei 2", "lei 3"]
    "primeiros 5 capitulos" -> ["capitulo 1", ..., "capitulo 5"]
    """
    q = _remove_accents(query.lower())
    patterns = [
        (r"\bprimeir[oa]s?\s+(\d+)\s+leis?\b", "lei"),
        (r"\bprimeir[oa]s?\s+(\d+)\s+cap[i]tulos?\b", "capitulo"),
        (r"\bprimeir[oa]s?\s+(\d+)\s+artigos?\b", "artigo"),
        (r"\b(\d+)\s+primeir[oa]s?\s+leis?\b", "lei"),
    ]
    extras = []
    for pat, entity in patterns:
        m = re.search(pat, q)
        if m:
            n = int(re.findall(r"\d+", m.group(0))[0])
            for i in range(1, min(n + 1, 16)):
                extras.append(entity + " " + str(i))
    return extras


def _expand_query(query: str) -> list:
    q = query.lower().strip()
    q_norm = _remove_accents(q)
    variants = [q]

    # ordinais por extenso -> numero
    for ordinal, num in _ORDINAL_MAP.items():
        if ordinal in q_norm:
            variant = q_norm.replace(ordinal, num)
            variants.append(variant.strip())
            variants.append(num)

    # "primeiras N leis" -> ["lei 1", "lei 2", ...]
    variants.extend(_expand_range(q))

    # numeros isolados
    for n in re.findall(r"\b(\d+)\b", q):
        variants.append(n)

    return list(dict.fromkeys(variants))


def _extract_keywords(query: str) -> list:
    stopwords = {
        "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
        "em", "no", "na", "nos", "nas", "por", "para", "com", "que", "e",
        "ou", "se", "me", "te", "lhe", "qual", "quais", "como", "onde",
        "quando", "porque", "mas", "mais", "muito", "bem", "ja", "sobre",
        "sabe", "dizer", "falar", "explique", "explica", "pode", "fala",
    }
    all_terms = []
    for variant in _expand_query(query):
        for t in re.findall(r"[\w]+", variant.lower()):
            if t not in stopwords and len(t) >= 1:
                all_terms.append(t)
    seen = set()
    keywords = []
    for t in all_terms:
        if t not in seen:
            seen.add(t)
            keywords.append(t)
    return keywords


class SearchService:
    """Busca hibrida: semantica + keyword com fusao por RRF."""

    @staticmethod
    async def search(
        db: AsyncSession,
        query: str,
        top_k: int = 8,
        document_id: UUID | None = None,
        min_similarity: float = 0.2,
    ) -> list:
        semantic_results = await SearchService._semantic_search(
            db, query, top_k=top_k * 2, document_id=document_id,
            min_similarity=min_similarity,
        )
        keyword_results = await SearchService._keyword_search(
            db, query, top_k=top_k * 2, document_id=document_id,
        )
        fused = SearchService._fuse_rrf(semantic_results, keyword_results, top_k=top_k)
        if fused:
            doc_ids = list({r.document_id for r in fused})
            docs_stmt = select(Document).where(Document.id.in_(doc_ids))
            docs_result = await db.execute(docs_stmt)
            docs_map = {doc.id: doc.filename for doc in docs_result.scalars().all()}
            for r in fused:
                r.document_filename = docs_map.get(r.document_id, "Desconhecido")
        return fused

    @staticmethod
    async def _semantic_search(db, query, top_k, document_id, min_similarity):
        embedding_service = get_embedding_service()
        query_vector = embedding_service.embed(query)
        base_filter = [Chunk.embedding.is_not(None)]
        if document_id:
            base_filter.append(Chunk.document_id == document_id)
        stmt = (
            select(
                Chunk,
                (1 - Chunk.embedding.cosine_distance(query_vector)).label("similarity"),
            )
            .where(*base_filter)
            .order_by(Chunk.embedding.cosine_distance(query_vector))
            .limit(top_k)
        )
        rows = (await db.execute(stmt)).all()
        return [
            SearchResult(chunk=chunk, similarity=float(sim), match_type="semantic")
            for chunk, sim in rows
            if float(sim) >= min_similarity
        ]

    @staticmethod
    async def _keyword_search(db, query, top_k, document_id):
        keywords = _extract_keywords(query)
        if not keywords:
            return []

        found = {}

        # Pass 0: full phrase variants (e.g. "lei 1", "lei 32")
        for phrase in _expand_query(query):
            phrase = phrase.strip()
            if len(phrase) < 2:
                continue
            cond_parts = ["c.embedding IS NOT NULL", "c.content ILIKE :kw"]
            params = {"kw": "%" + phrase + "%", "limit": top_k}
            if document_id:
                cond_parts.append("c.document_id = :doc_id")
                params["doc_id"] = str(document_id)
            where_clause = " AND ".join(cond_parts)
            sql = text(
                "SELECT c.id, c.document_id, c.content, c.chunk_index, "
                "0.85 AS similarity FROM chunks c "
                "WHERE " + where_clause + " ORDER BY c.chunk_index LIMIT :limit"
            )
            rows = (await db.execute(sql, params)).fetchall()
            for row in rows:
                cid = str(row.id)
                if cid not in found:
                    found[cid] = SearchResult(chunk=_RowChunk(row), similarity=0.85, match_type="keyword")

        # Pass 1: individual keywords ILIKE
        for kw in keywords:
            cond_parts = ["c.embedding IS NOT NULL", "c.content ILIKE :kw"]
            params = {"kw": "%" + kw + "%", "limit": top_k}
            if document_id:
                cond_parts.append("c.document_id = :doc_id")
                params["doc_id"] = str(document_id)
            where_clause = " AND ".join(cond_parts)
            sql = text(
                "SELECT c.id, c.document_id, c.content, c.chunk_index, "
                "0.7 AS similarity FROM chunks c "
                "WHERE " + where_clause + " ORDER BY c.chunk_index LIMIT :limit"
            )
            rows = (await db.execute(sql, params)).fetchall()
            for row in rows:
                cid = str(row.id)
                if cid not in found:
                    found[cid] = SearchResult(chunk=_RowChunk(row), similarity=0.7, match_type="keyword")

        # Pass 2: PostgreSQL full-text search
        ts_query_str = " | ".join(keywords)
        tsvec_cond = "to_tsvector('portuguese', c.content) @@ to_tsquery('portuguese', :tsq)"
        try:
            cond_parts = ["c.embedding IS NOT NULL", tsvec_cond]
            params = {"tsq": ts_query_str, "limit": top_k}
            if document_id:
                cond_parts.append("c.document_id = :doc_id")
                params["doc_id"] = str(document_id)
            where_clause = " AND ".join(cond_parts)
            sql = text(
                "SELECT c.id, c.document_id, c.content, c.chunk_index, "
                "ts_rank(to_tsvector('portuguese', c.content), "
                "to_tsquery('portuguese', :tsq)) AS similarity "
                "FROM chunks c WHERE " + where_clause + " ORDER BY similarity DESC LIMIT :limit"
            )
            rows = (await db.execute(sql, params)).fetchall()
            for row in rows:
                cid = str(row.id)
                if cid not in found:
                    found[cid] = SearchResult(
                        chunk=_RowChunk(row), similarity=float(row.similarity), match_type="keyword"
                    )
        except Exception:
            pass

        return list(found.values())[:top_k]

    @staticmethod
    def _fuse_rrf(semantic, keyword, top_k, rrf_k=60):
        scores = {}
        results = {}
        for rank, r in enumerate(semantic):
            cid = str(r.chunk_id)
            scores[cid] = scores.get(cid, 0.0) + _rrf_score(rank, rrf_k)
            results[cid] = r
        for rank, r in enumerate(keyword):
            cid = str(r.chunk_id)
            scores[cid] = scores.get(cid, 0.0) + _rrf_score(rank, rrf_k)
            if cid not in results:
                results[cid] = r
            else:
                results[cid].match_type = "hybrid"
        sorted_ids = sorted(scores, key=lambda k: scores[k], reverse=True)[:top_k]
        fused = []
        for cid in sorted_ids:
            r = results[cid]
            r.similarity = round(scores[cid], 4)
            fused.append(r)
        return fused


class _RowChunk:
    """Proxy para simular Chunk a partir de row SQL bruta."""
    def __init__(self, row):
        self.id = row.id
        self.document_id = row.document_id
        self.content = row.content
        self.chunk_index = row.chunk_index
