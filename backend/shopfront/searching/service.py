"""High-level search orchestration for live search and catalog discovery.

Views use this module instead of talking to OpenSearch directly. It encapsulates
query rewrites, provider selection, lexical fallback, semantic candidate
collection, and simple reranking heuristics.
"""

from dataclasses import dataclass, field
from difflib import get_close_matches
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache

from django.db.models import Q

from catalog.models import Brand, Category, Product, Tag
from . import backend as es_search


@dataclass
class SearchBundle:
    """Normalized result bundle returned by every search provider."""
    product_ids: list[int]
    countries: list[str]
    suggestions: list[str]
    provider: str
    rewritten_query: str = ""
    effective_query: str = ""
    rewrite_kind: str = ""
    query_variants: list[str] = field(default_factory=list)


SEARCH_SYNONYMS = {
    "сиропы": "сироп",
    "стаканы": "стакан",
    "бокалы": "бокал",
    "кофе зерно": "кофе",
    "салфетки": "салфетка",
    "одноразка": "одноразовая посуда",
}

SEMANTIC_QUERY_REWRITES = {
    "одноразка": "одноразовая посуда",
    "хозка": "расходные материалы",
    "барный сироп": "сироп для бара",
    "кофе для эспрессо": "зерновой кофе эспрессо",
    "упаковка на вынос": "takeaway упаковка",
}

_EN_TO_RU_LAYOUT = str.maketrans(
    {
        "q": "й", "w": "ц", "e": "у", "r": "к", "t": "е", "y": "н", "u": "г", "i": "ш", "o": "щ", "p": "з",
        "[": "х", "]": "ъ", "a": "ф", "s": "ы", "d": "в", "f": "а", "g": "п", "h": "р", "j": "о", "k": "л",
        "l": "д", ";": "ж", "'": "э", "z": "я", "x": "ч", "c": "с", "v": "м", "b": "и", "n": "т", "m": "ь",
        ",": "б", ".": "ю", "/": ".",
    }
)

def _normalize_query(query: str) -> str:
    """Internal helper for normalize query."""
    return " ".join((query or "").strip().lower().split())


def keyboard_layout_correction(query: str) -> str:
    """Best-effort keyboard layout correction for mistyped ru/en queries."""
    normalized = _normalize_query(query)
    if not normalized or not getattr(settings, "SEARCH_KEYBOARD_LAYOUT_CORRECTION_ENABLED", True):
        return normalized
    has_latin = any("a" <= ch <= "z" for ch in normalized)
    has_cyrillic = any("а" <= ch <= "я" or ch == "ё" for ch in normalized)
    if has_latin and not has_cyrillic:
        corrected = normalized.translate(_EN_TO_RU_LAYOUT)
        return corrected or normalized
    return normalized


def build_query_variants(query: str) -> list[str]:
    """Build lexical query variants from direct synonym substitutions."""
    normalized = _normalize_query(query)
    if not normalized:
        return []
    variants = [normalized]
    corrected = keyboard_layout_correction(normalized)
    if corrected and corrected not in variants:
        variants.append(corrected)
    alias = SEARCH_SYNONYMS.get(normalized)
    if alias and alias not in variants:
        variants.append(alias)
    corrected_alias = SEARCH_SYNONYMS.get(corrected)
    if corrected_alias and corrected_alias not in variants:
        variants.append(corrected_alias)
    for source, target in SEARCH_SYNONYMS.items():
        if source in normalized:
            replaced = normalized.replace(source, target).strip()
            if replaced and replaced not in variants:
                variants.append(replaced)
        if corrected and source in corrected:
            replaced = corrected.replace(source, target).strip()
            if replaced and replaced not in variants:
                variants.append(replaced)
    return variants[:4]


def rewrite_query(query: str) -> str:
    """Rewrite shorthand phrases into more catalog-friendly search terms."""
    normalized = _normalize_query(query)
    if not getattr(settings, "SEARCH_QUERY_REWRITE_ENABLED", True):
        return normalized
    if not normalized:
        return ""
    rewritten = normalized
    for source, target in SEMANTIC_QUERY_REWRITES.items():
        if source in rewritten:
            rewritten = rewritten.replace(source, target).strip()
    return rewritten


def semantic_query_variants(query: str) -> list[str]:
    """Expand a query for semantic fallback matching in the database."""
    normalized = _normalize_query(query)
    if not normalized:
        return []
    variants = build_query_variants(normalized)
    rewritten = rewrite_query(normalized)
    if rewritten and rewritten not in variants:
        variants.append(rewritten)
    tokens = [token for token in rewritten.split() if len(token) >= 3]
    for token in tokens:
        if token not in variants:
            variants.append(token)
    return variants[:8]


def suggest_query_corrections(query: str, limit: int = 5) -> list[str]:
    """Suggest alternative queries from cached catalog vocabulary."""
    normalized = " ".join((query or "").strip().split())
    if len(normalized) < 3:
        return []
    direct_variants = [
        variant for variant in build_query_variants(normalized)
        if variant.casefold() != normalized.casefold()
    ]
    candidates = []
    if getattr(settings, "CACHE_SUGGESTION_CANDIDATES", True):
        candidates = cache.get("shopfront:search:suggestion_candidates:v1") or []
    if not candidates:
        candidates.extend(list(Brand.objects.order_by("name").values_list("name", flat=True)[:100]))
        candidates.extend(list(Category.objects.order_by("name").values_list("name", flat=True)[:120]))
        candidates.extend(list(Tag.objects.order_by("name").values_list("name", flat=True)[:80]))
        candidates.extend(list(Product.objects.order_by("-is_new", "name").values_list("name", flat=True)[:150]))
        if getattr(settings, "CACHE_SUGGESTION_CANDIDATES", True):
            cache.set(
                "shopfront:search:suggestion_candidates:v1",
                candidates,
                timeout=int(getattr(settings, "SEARCH_SUGGESTION_CACHE_TTL", 900)),
            )
    seen = set()
    deduped = []
    for item in candidates:
        key = str(item or "").strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(str(item).strip())
    close = get_close_matches(normalized, deduped, n=limit, cutoff=0.62)
    merged = []
    merged_seen = set()
    for item in direct_variants + [item for item in close if item.casefold() != normalized.casefold()]:
        key = item.casefold()
        if key in merged_seen:
            continue
        merged_seen.add(key)
        merged.append(item)
    return merged[:limit]


class SearchProvider:
    """Abstract provider interface consumed by shopfront search flows."""
    code = "base"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        raise NotImplementedError


class OpenSearchSearchProvider(SearchProvider):
    """Search provider backed by the low-level OpenSearch client."""
    code = "opensearch"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        effective_query = _normalize_query(query)
        raw = es_search.live_search_bundle(query=effective_query, limit=limit, country_limit=country_limit)
        if len(raw) == 3:
            ids, countries, suggestions = raw
        else:
            ids, countries = raw
            suggestions = []
        rewritten = rewrite_query(query)
        rewrite_kind = []
        if rewritten and rewritten != effective_query:
            rewrite_kind.append("semantic_rewrite")
        return SearchBundle(
            product_ids=list(ids),
            countries=list(countries),
            suggestions=list(suggestions),
            provider=self.code,
            rewritten_query=rewritten,
            effective_query=effective_query,
            rewrite_kind="+".join(rewrite_kind),
            query_variants=semantic_query_variants(query),
        )


class DatabaseSearchProvider(SearchProvider):
    """ORM-based provider used as a fallback when search infra is unavailable."""
    code = "database"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        variants = semantic_query_variants(query) or [query]
        effective_query = _normalize_query(query)
        rewritten = rewrite_query(query)
        rewrite_kind = []
        if rewritten and rewritten != effective_query:
            rewrite_kind.append("semantic_rewrite")
        query_filter = Q()
        for variant in variants:
            query_filter |= (
                Q(name__icontains=variant)
                | Q(sku__icontains=variant)
                | Q(manufacturer_sku__icontains=variant)
                | Q(barcode__icontains=variant)
                | Q(brand__name__icontains=variant)
                | Q(category__name__icontains=variant)
            )
        qs = (
            Product.objects.filter(
                query_filter
            )
            .distinct()
            .order_by("-is_new", "name")
        )
        ids = list(qs.values_list("id", flat=True)[:limit])
        suggestions = []
        seen = set()
        for product in qs[:limit]:
            for candidate in (product.name, product.sku, product.manufacturer_sku):
                normalized = " ".join(str(candidate or "").split())
                if not normalized:
                    continue
                key = normalized.casefold()
                if key in seen:
                    continue
                seen.add(key)
                suggestions.append(normalized)
        if not suggestions:
            suggestions.extend(suggest_query_corrections(query, limit=limit))
        return SearchBundle(
            product_ids=ids,
            countries=[],
            suggestions=suggestions[:limit],
            provider=self.code,
            rewritten_query=rewritten,
            effective_query=effective_query,
            rewrite_kind="+".join(rewrite_kind),
            query_variants=variants[:],
        )


def _semantic_candidate_ids(query: str, limit: int = 24) -> list[int]:
    """Collect broader candidate ids from semantic-ish ORM matching."""
    variants = semantic_query_variants(query)
    if not variants:
        return []
    query_filter = Q()
    for variant in variants:
        query_filter |= (
            Q(name__icontains=variant)
            | Q(brand__name__icontains=variant)
            | Q(category__name__icontains=variant)
            | Q(tags__name__icontains=variant)
            | Q(description__icontains=variant)
            | Q(material__icontains=variant)
            | Q(purpose__icontains=variant)
            | Q(flavor__icontains=variant)
        )
    return list(
        Product.objects.filter(query_filter)
        .distinct()
        .order_by("-is_promo", "-is_new", "name")
        .values_list("id", flat=True)[:limit]
    )


def _rerank_product_ids(product_ids: list[int], query: str, limit: int = 8) -> list[int]:
    """Apply lightweight heuristic reranking to merged lexical and semantic ids."""
    if not product_ids:
        return []
    if not getattr(settings, "SEARCH_RERANK_ENABLED", True):
        return product_ids[:limit]
    normalized = " ".join((query or "").strip().lower().split())
    rewritten = rewrite_query(query)
    tokens = [token for token in rewritten.split() if token]
    rows = Product.objects.filter(id__in=product_ids).select_related("brand", "category").only(
        "id",
        "name",
        "description",
        "material",
        "purpose",
        "is_promo",
        "is_new",
        "brand__name",
        "category__name",
    )
    input_positions = {pid: pos for pos, pid in enumerate(product_ids)}
    scores: dict[int, float] = defaultdict(float)
    for position, pid in enumerate(product_ids):
        scores[pid] += max(0, 40 - position)
    for product in rows:
        haystacks = [
            (product.name or "").lower(),
            (getattr(product.brand, "name", "") or "").lower(),
            (getattr(product.category, "name", "") or "").lower(),
            (product.description or "").lower(),
            (product.material or "").lower(),
            (product.purpose or "").lower(),
        ]
        full = " ".join(haystacks)
        if normalized and normalized in full:
            scores[product.id] += 30
        if rewritten and rewritten != normalized and rewritten in full:
            scores[product.id] += 20
        for token in tokens:
            if token in full:
                scores[product.id] += 6
        if product.is_promo:
            scores[product.id] += 1.5
        if product.is_new:
            scores[product.id] += 1
    ordered = sorted(product_ids, key=lambda pid: (-scores[pid], input_positions[pid]))
    seen = set()
    result = []
    for pid in ordered:
        if pid in seen:
            continue
        seen.add(pid)
        result.append(pid)
        if len(result) >= limit:
            break
    return result


class HybridSearchProvider(SearchProvider):
    """Provider that merges OpenSearch lexical recall with semantic DB recall."""
    code = "hybrid"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        rewritten = rewrite_query(query)
        effective_query = _normalize_query(query)
        rewrite_kind = []
        if rewritten and rewritten != effective_query:
            rewrite_kind.append("semantic_rewrite")
        try:
            lexical_bundle = OpenSearchSearchProvider().live_bundle(
                query=query,
                limit=max(limit * 2, 12),
                country_limit=country_limit,
            )
        except es_search.OpenSearchUnavailable:
            lexical_bundle = DatabaseSearchProvider().live_bundle(query=query, limit=max(limit * 2, 12), country_limit=country_limit)
        semantic_ids = _semantic_candidate_ids(rewritten or query, limit=max(limit * 3, 24))
        merged = []
        seen = set()
        for pid in lexical_bundle.product_ids + semantic_ids:
            if pid in seen:
                continue
            seen.add(pid)
            merged.append(pid)
        reranked_ids = _rerank_product_ids(merged, rewritten or query, limit=limit)
        suggestions = list(lexical_bundle.suggestions)
        if rewritten and rewritten not in suggestions and rewritten.casefold() != (query or "").strip().casefold():
            suggestions.insert(0, rewritten)
        for candidate in suggest_query_corrections(query, limit=limit):
            if candidate not in suggestions:
                suggestions.append(candidate)
        return SearchBundle(
            product_ids=reranked_ids,
            countries=lexical_bundle.countries,
            suggestions=suggestions[:limit],
            provider=self.code,
            rewritten_query=rewritten,
            effective_query=effective_query,
            rewrite_kind="+".join(rewrite_kind),
            query_variants=semantic_query_variants(query),
        )


def get_search_provider(prefer_semantic: bool = False) -> SearchProvider:
    """Resolve the active search provider from settings and feature flags."""
    provider_code = getattr(settings, "SEARCH_PROVIDER", "opensearch")
    if prefer_semantic or getattr(settings, "SEMANTIC_SEARCH_ENABLED", False):
        return HybridSearchProvider()
    if provider_code == "hybrid":
        return HybridSearchProvider()
    if provider_code == "database":
        return DatabaseSearchProvider()
    return OpenSearchSearchProvider()
