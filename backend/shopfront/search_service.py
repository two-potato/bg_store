from dataclasses import dataclass
from difflib import get_close_matches
from collections import defaultdict

from django.conf import settings

from django.db.models import Q

from catalog.models import Brand, Category, Product, Tag
from . import search as es_search


@dataclass
class SearchBundle:
    product_ids: list[int]
    countries: list[str]
    suggestions: list[str]
    provider: str
    rewritten_query: str = ""


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


def build_query_variants(query: str) -> list[str]:
    normalized = " ".join((query or "").strip().lower().split())
    if not normalized:
        return []
    variants = [normalized]
    alias = SEARCH_SYNONYMS.get(normalized)
    if alias and alias not in variants:
        variants.append(alias)
    for source, target in SEARCH_SYNONYMS.items():
        if source in normalized:
            replaced = normalized.replace(source, target).strip()
            if replaced and replaced not in variants:
                variants.append(replaced)
    return variants[:4]


def rewrite_query(query: str) -> str:
    if not getattr(settings, "SEARCH_QUERY_REWRITE_ENABLED", True):
        return " ".join((query or "").strip().lower().split())
    normalized = " ".join((query or "").strip().lower().split())
    if not normalized:
        return ""
    rewritten = normalized
    for source, target in SEMANTIC_QUERY_REWRITES.items():
        if source in rewritten:
            rewritten = rewritten.replace(source, target).strip()
    return rewritten


def semantic_query_variants(query: str) -> list[str]:
    normalized = " ".join((query or "").strip().lower().split())
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
    normalized = " ".join((query or "").strip().split())
    if len(normalized) < 3:
        return []
    direct_variants = [
        variant for variant in build_query_variants(normalized)
        if variant.casefold() != normalized.casefold()
    ]
    candidates = []
    candidates.extend(list(Brand.objects.order_by("name").values_list("name", flat=True)[:100]))
    candidates.extend(list(Category.objects.order_by("name").values_list("name", flat=True)[:120]))
    candidates.extend(list(Tag.objects.order_by("name").values_list("name", flat=True)[:80]))
    candidates.extend(list(Product.objects.order_by("-is_new", "name").values_list("name", flat=True)[:150]))
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
    code = "base"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        raise NotImplementedError


class ElasticsearchSearchProvider(SearchProvider):
    code = "elasticsearch"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        raw = es_search.live_search_bundle(query=query, limit=limit, country_limit=country_limit)
        if len(raw) == 3:
            ids, countries, suggestions = raw
        else:
            ids, countries = raw
            suggestions = []
        return SearchBundle(
            product_ids=list(ids),
            countries=list(countries),
            suggestions=list(suggestions),
            provider=self.code,
            rewritten_query=rewrite_query(query),
        )


class DatabaseSearchProvider(SearchProvider):
    code = "database"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        variants = semantic_query_variants(query) or [query]
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
            rewritten_query=rewrite_query(query),
        )


def _semantic_candidate_ids(query: str, limit: int = 24) -> list[int]:
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
    if not product_ids:
        return []
    if not getattr(settings, "SEARCH_RERANK_ENABLED", True):
        return product_ids[:limit]
    normalized = " ".join((query or "").strip().lower().split())
    rewritten = rewrite_query(query)
    tokens = [token for token in rewritten.split() if token]
    rows = Product.objects.filter(id__in=product_ids).select_related("brand", "category")
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
    ordered = sorted(product_ids, key=lambda pid: (-scores[pid], product_ids.index(pid)))
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
    code = "hybrid"

    def live_bundle(self, query: str, limit: int = 8, country_limit: int = 6) -> SearchBundle:
        rewritten = rewrite_query(query)
        try:
            lexical_bundle = ElasticsearchSearchProvider().live_bundle(query=query, limit=max(limit * 2, 12), country_limit=country_limit)
        except Exception:
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
        )


def get_search_provider(prefer_semantic: bool = False) -> SearchProvider:
    provider_code = getattr(settings, "SEARCH_PROVIDER", "elasticsearch")
    if prefer_semantic or getattr(settings, "SEMANTIC_SEARCH_ENABLED", False):
        return HybridSearchProvider()
    if provider_code == "hybrid":
        return HybridSearchProvider()
    if provider_code == "database":
        return DatabaseSearchProvider()
    try:
        return ElasticsearchSearchProvider()
    except Exception:
        return DatabaseSearchProvider()
