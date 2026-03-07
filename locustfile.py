from locust import HttpUser, between, task


class ShopUser(HttpUser):
    wait_time = between(0.2, 1.5)

    @task(4)
    def open_home(self):
        self.client.get("/", name="GET /")

    @task(3)
    def open_catalog(self):
        self.client.get("/catalog/", name="GET /catalog/")

    @task(2)
    def open_about(self):
        self.client.get("/about/", name="GET /about/")

    @task(1)
    def healthcheck(self):
        self.client.get("/health/", name="GET /health/")
