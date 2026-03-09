import random
import os
from urllib.parse import quote_plus

from locust import HttpUser, LoadTestShape, between, task

FALLBACK_SLUGS = [
    "poetic-product-20002265",
    "poetic-product-20001803",
    "poetic-product-20003244",
]
SEARCH_TERMS = [
    "кофе",
    "сироп",
    "стакан",
    "шоколад",
    "арабика",
    "крышка",
    "зерно",
    "молоко",
]


def _parse_stages(raw: str) -> list[tuple[int, int]]:
    """
    Format:
      STAIRCASE_STAGES="50x90;100x90;150x90"
      means users=50 for 90s, then 100 for 90s, etc.
    """
    stages: list[tuple[int, int]] = []
    for part in (raw or "").split(";"):
        p = part.strip().lower()
        if not p:
            continue
        if "x" not in p:
            continue
        users_s, dur_s = p.split("x", 1)
        try:
            users = int(users_s.strip())
            dur = int(dur_s.strip())
        except ValueError:
            continue
        if users > 0 and dur > 0:
            stages.append((users, dur))
    return stages


class ProdMarketplaceUser(HttpUser):
    wait_time = between(0.15, 0.8)
    product_slugs: list[str] = FALLBACK_SLUGS

    @task(8)
    def homepage(self):
        self.client.get("/", name="GET /")

    @task(10)
    def catalog(self):
        variants = [
            "/catalog/",
            "/catalog/?sort=rating_desc",
            "/catalog/?is_new=1",
            "/catalog/?sort=price_asc",
            "/catalog/?sort=price_desc",
            "/catalog/?sort=promo",
            "/catalog/?sort=popular",
        ]
        self.client.get(random.choice(variants), name="GET /catalog/*")

    @task(6)
    def product_detail(self):
        slug = random.choice(self.__class__.product_slugs)
        self.client.get(f"/product/{slug}/", name="GET /product/:slug/")

    @task(4)
    def live_search(self):
        q = quote_plus(random.choice(SEARCH_TERMS))
        self.client.get(f"/search/live/?q={q}", name="GET /search/live/")

    @task(3)
    def service_pages(self):
        self.client.get(random.choice(["/delivery/", "/contacts/", "/about/"]), name="GET /page")

    @task(3)
    def cart_badge(self):
        self.client.get("/cart/badge/", name="GET /cart/badge/")

    @task(1)
    def health(self):
        self.client.get("/health/", name="GET /health/")


class StaircaseShape(LoadTestShape):
    stages = _parse_stages(os.getenv("STAIRCASE_STAGES", ""))
    spawn_rate = float(os.getenv("STAIRCASE_SPAWN_RATE", "20"))

    def tick(self):
        if not self.stages:
            return None
        run_time = int(self.get_run_time())
        elapsed = 0
        for users, duration in self.stages:
            elapsed += duration
            if run_time < elapsed:
                return (users, self.spawn_rate)
        return None
