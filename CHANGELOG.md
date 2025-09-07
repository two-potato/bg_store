## Unreleased (ref branch)

- Catalog: add SEO fields to Brand, Series, Category, Product.
- Catalog: add Color and Country models; switch Product.color and Product.country_of_origin to FKs.
- Catalog: enforce 8-digit numeric SKU; enforce max 10 images per product.
- Catalog API: expose color and country as names in ProductSerializer for backward compatibility.
- Seed: update to use numeric 8-digit SKUs, create basic Color/Country records.
- Users: add Friendship model; add `photo` to UserProfile; register Friendship in admin.

