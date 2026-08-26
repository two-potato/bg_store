"""Catalog and filter suggestion UI views."""

from __future__ import annotations

import time

from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View

from core.logging_utils import log_calls

from ..catalog_page_service import (
    DEFAULT_CATALOG_HTML_CACHE_KEY,
    DEFAULT_CATALOG_HTML_CACHE_TIMEOUT,
    CatalogPageService,
)
from .constants import log
from .utils_catalog import (
    CatalogRequestParams,
    _cache_set,
    _cached_catalog_brands,
    _cached_catalog_categories,
    _cached_catalog_tags,
    _catalog_filter_suggestion_limit,
    _category_breadcrumb_label_map,
    _category_path,
)


class CatalogView(View):
    @log_calls(log)
    def get(self, request):
        """Render catalog listing with filters, ranking, facets, and SEO metadata."""
        get_token(request)
        params = CatalogRequestParams.from_request(request)
        plan = CatalogPageService(request, params=params, started_at=time.perf_counter()).build()
        if plan.cached_html is not None:
            return HttpResponse(plan.cached_html)
        if plan.append_fragment_context is not None:
            return render(request, "shopfront/partials/catalog_grid_append.html", plan.append_fragment_context)
        if plan.cacheable_default_catalog:
            html = render_to_string("shopfront/catalog.html", plan.context, request=request)
            _cache_set(
                DEFAULT_CATALOG_HTML_CACHE_KEY,
                html,
                timeout=DEFAULT_CATALOG_HTML_CACHE_TIMEOUT,
            )
            return HttpResponse(html)
        return render(request, "shopfront/catalog.html", plan.context)


class CatalogFilterSuggestionsView(View):
    @log_calls(log)
    def get(self, request):
        """Return type-specific autocomplete options for catalog filter controls."""
        kind = (request.GET.get("kind") or "").strip().lower()
        query = " ".join((request.GET.get("q") or "").strip().split())
        limit = _catalog_filter_suggestion_limit()
        if kind not in {"brand", "category", "tag"}:
            return JsonResponse({"items": [], "error": "invalid_kind"}, status=400)
        if len(query) < 2:
            return JsonResponse({"items": []})

        normalized_query = query.casefold()
        items = []
        seen = set()

        if kind == "brand":
            for brand in _cached_catalog_brands():
                name = (brand.name or "").strip()
                if not name or normalized_query not in name.casefold():
                    continue
                key = name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": str(brand.id), "label": name, "hint": f"ID {brand.id}"})
                if len(items) >= limit:
                    break
        elif kind == "tag":
            for tag_obj in _cached_catalog_tags():
                name = (tag_obj.name or "").strip()
                slug = (tag_obj.slug or "").strip()
                haystacks = [name.casefold(), slug.casefold()]
                if not any(normalized_query in haystack for haystack in haystacks if haystack):
                    continue
                key = slug or name.casefold()
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": slug or str(tag_obj.id), "label": name, "hint": slug})
                if len(items) >= limit:
                    break
        else:
            categories = _cached_catalog_categories()
            breadcrumb_map = _category_breadcrumb_label_map(categories)
            for category in categories:
                name = (category.name or "").strip()
                slug = (_category_path(category) or "").strip()
                breadcrumb = breadcrumb_map.get(category.id, name)
                haystacks = [name.casefold(), slug.casefold(), breadcrumb.casefold()]
                if not any(normalized_query in haystack for haystack in haystacks if haystack):
                    continue
                key = slug or str(category.id)
                if key in seen:
                    continue
                seen.add(key)
                items.append({"value": slug or str(category.id), "label": name, "hint": breadcrumb})
                if len(items) >= limit:
                    break

        return JsonResponse({"items": items})
