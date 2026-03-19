import pytest

from shopfront.catalog_selectors import category_descendant_ids, category_option_rows
from catalog.models import Category


pytestmark = pytest.mark.django_db


def test_category_descendant_ids_returns_tree_depth():
    root = Category.objects.create(name="Root", slug="root")
    child = Category.objects.create(name="Child", slug="child", parent=root)
    grand = Category.objects.create(name="Grand", slug="grand", parent=child)

    ids = category_descendant_ids(root)

    assert root.id in ids
    assert child.id in ids
    assert grand.id in ids


def test_category_option_rows_preserves_depth_labels():
    root = Category.objects.create(name="Root", slug="root")
    child = Category.objects.create(name="Child", slug="child", parent=root)

    rows = category_option_rows([root, child])

    assert rows[0]["depth"] == 0
    assert rows[0]["name"] == "Root"
    assert rows[1]["depth"] == 1
    assert rows[1]["name"] == "Child"
