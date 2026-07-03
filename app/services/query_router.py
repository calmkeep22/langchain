import re
from enum import Enum

_SYMBOL_PATTERNS = [
    re.compile(r"[A-Za-z_][A-Za-z0-9_]*\("),  # function call: foo(
    re.compile(r"\b[A-Z][A-Za-z0-9]*\.[A-Za-z_][A-Za-z0-9_]*\b"),  # Class.method
    re.compile(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b"),  # ALL_CAPS constant / error code (needs "_")
    re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){1,}\b"),  # snake_case identifier
]

_ARCHITECTURE_KEYWORDS = ("흐름", "구조", "아키텍처", "전체", "연결", "과정", "파이프라인")


class QueryType(str, Enum):
    SYMBOL = "symbol"
    NATURAL_LANGUAGE = "natural_language"
    ARCHITECTURE = "architecture"


def classify_query(question: str) -> QueryType:
    """Cheap regex/keyword routing -- no LLM call, so it's free and instant.

    SYMBOL: the question names a specific identifier (function call, dotted
    Class.method, ALL_CAPS constant/error code, or snake_case name) -- exact
    keyword matching (BM25) should be trusted more than embedding similarity.

    ARCHITECTURE: the question asks about an overall flow/structure spanning
    multiple files -- retrieval should be broader (larger top_k) rather than
    narrowly precise.

    Everything else is treated as a general NATURAL_LANGUAGE question, using
    the default balanced dense+BM25 weighting.
    """
    if any(pattern.search(question) for pattern in _SYMBOL_PATTERNS):
        return QueryType.SYMBOL
    if any(keyword in question for keyword in _ARCHITECTURE_KEYWORDS):
        return QueryType.ARCHITECTURE
    return QueryType.NATURAL_LANGUAGE


def routing_params(query_type: QueryType) -> dict:
    """How each query type should adjust the hybrid search call.

    SYMBOL: sparse_weight is kept at 1.0 (not boosted) for now. Boosting BM25
    for symbol queries backfires when the identifier is embedded in a casual
    Korean question (e.g. "response_model이랑 ... 차이가 뭐야?") -- particles
    and question words like "차이가"/"뭐야" survive tokenization as whole
    tokens and out-rank the real identifier by BM25 IDF (see #29). Revisit
    once BM25 tokenization does proper Korean morphological analysis.
    ARCHITECTURE: widen retrieval since a flow/structure question usually
    needs evidence from more than a couple of chunks.
    """
    if query_type == QueryType.SYMBOL:
        return {"dense_weight": 1.0, "sparse_weight": 1.0, "top_k_multiplier": 1}
    if query_type == QueryType.ARCHITECTURE:
        return {"dense_weight": 1.0, "sparse_weight": 1.0, "top_k_multiplier": 2}
    return {"dense_weight": 1.0, "sparse_weight": 1.0, "top_k_multiplier": 1}
