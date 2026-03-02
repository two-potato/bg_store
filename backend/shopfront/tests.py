from django.test import TestCase

from catalog.models import Brand, Category, Product, Series


class CartHtmxBadgeTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="Brand T")
        series = Series.objects.create(brand=brand, name="Series T")
        category = Category.objects.create(name="Category T")
        self.product = Product.objects.create(
            sku="12345678",
            name="Product T",
            brand=brand,
            series=series,
            category=category,
            price="100.00",
            stock_qty=20,
        )

    def test_add_returns_oob_badge_fragment_and_trigger(self):
        resp = self.client.post("/cart/add/", {"product_id": self.product.id, "qty": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id="cart-badge"', resp.text)
        self.assertIn('hx-swap-oob="outerHTML"', resp.text)
        self.assertIn("cartChanged", resp.headers.get("HX-Trigger", ""))

    def test_badge_reflects_latest_count_and_total(self):
        self.client.post("/cart/add/", {"product_id": self.product.id, "qty": 2})
        resp = self.client.get("/cart/badge/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('data-count="2"', resp.text)
        self.assertIn("200", resp.text)

        self.client.post("/cart/update/", {"product_id": self.product.id, "op": "inc"})
        resp2 = self.client.get("/cart/badge/")
        self.assertIn('data-count="3"', resp2.text)
        self.assertIn("300", resp2.text)

    def test_update_remove_clear_include_oob_badge(self):
        self.client.post("/cart/add/", {"product_id": self.product.id, "qty": 1})

        r_update = self.client.post("/cart/update/", {"product_id": self.product.id, "op": "inc"})
        self.assertEqual(r_update.status_code, 200)
        self.assertIn('hx-swap-oob="outerHTML"', r_update.text)

        r_remove = self.client.post("/cart/remove/", {"product_id": str(self.product.id)})
        self.assertEqual(r_remove.status_code, 200)
        self.assertIn('hx-swap-oob="outerHTML"', r_remove.text)

        r_clear = self.client.post("/cart/clear/")
        self.assertEqual(r_clear.status_code, 200)
        self.assertIn('hx-swap-oob="outerHTML"', r_clear.text)
