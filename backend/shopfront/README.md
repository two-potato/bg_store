# Shopfront Module Map

`shopfront` reorganized into domain packages with canonical imports.

## New Domain Packages

- `shopfront/searching/`
  - `backend.py`: low-level OpenSearch adapter
  - `service.py`: high-level search orchestration
  - `observability.py`: search metrics and logs
  - `attribution.py`: session attribution for search events
  - `live.py`: live search context assembly

- `shopfront/recommendation/`
  - `service.py`: orchestration entrypoint for recommendation surfaces
  - `selectors.py`: candidate retrieval selectors
  - `ranker.py`: heuristic ranking logic
  - `scoring_service.py`: scoring contract layer (heuristic/ML)
  - `ml.py`: model training/inference helpers
  - `feature_store.py`: feature snapshot builders
  - `heuristics.py`: legacy heuristic recommendation helpers
  - `candidates.py`, `events.py`, `experiments.py`, `policy.py`, `observability.py`, `attribution_service.py`

## Placement Rules

- New search code: add under `shopfront/searching/`
- New recommendation code: add under `shopfront/recommendation/`
- Keep imports on canonical package paths only.
