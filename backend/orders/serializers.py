from rest_framework import serializers
from drf_spectacular.utils import OpenApiExample, extend_schema_serializer
from django.db import transaction
from django.db.models import Prefetch
from .models import Order, OrderItem, OrderSellerSplit, SellerOrder, SellerOrderItem, Shipment, ShipmentItem
from catalog.models import Product
from catalog.offer_service import active_offer_queryset, resolve_product_offer
from commerce.models import DeliveryAddress, LegalEntityMembership
from commerce.company_service import resolve_order_approval_requirement
from promotions.services import create_redemption, resolve_checkout_discount
from .services import plan_seller_splits


def _resolve_products_map(product_ids):
    unique_ids = list(dict.fromkeys(int(product_id) for product_id in product_ids))
    products = (
        Product.objects.filter(id__in=unique_ids)
        .prefetch_related(Prefetch("seller_offers", queryset=active_offer_queryset()))
    )
    return {product.id: product for product in products}


def _resolve_order_lines(items, products_map):
    lines = []
    for item in items:
        product = products_map[item["product_id"]]
        qty = int(item["qty"])
        offer = resolve_product_offer(product)
        price = offer.price if offer else product.price
        lines.append(
            {
                "product": product,
                "qty": qty,
                "offer": offer,
                "price": price,
                "row_total": price * qty,
            }
        )
    return lines

@extend_schema_serializer(
    examples=[OpenApiExample("Order line", value={"product_id": 101, "qty": 2}, request_only=True)]
)
class OrderItemInCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(help_text="ID товара из `/api/catalog/products/`")
    qty = serializers.IntegerField(min_value=1, help_text="Количество товара")


class OrderSellerSplitSerializer(serializers.ModelSerializer):
    seller = serializers.SlugRelatedField(read_only=True, slug_field="username")
    status = serializers.ChoiceField(
        choices=OrderSellerSplit.Status.choices,
        read_only=True,
        help_text="Статус распределения заказа по продавцу: planned, ready, sent",
    )

    class Meta:
        model = OrderSellerSplit
        fields = ["seller", "seller_store_name", "items_count", "subtotal", "status"]


class ShipmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentItem
        fields = ["seller_order_item", "qty"]


class ShipmentSerializer(serializers.ModelSerializer):
    items = ShipmentItemSerializer(many=True, read_only=True)
    delivery_method = serializers.ChoiceField(
        choices=Order.DeliveryMethod.choices,
        read_only=True,
        help_text="Способ доставки: courier или pickup",
    )

    class Meta:
        model = Shipment
        fields = ["id", "tracking_number", "delivery_method", "warehouse_name", "status", "packed_at", "shipped_at", "delivered_at", "items"]


class SellerOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SellerOrderItem
        fields = ["id", "product", "seller_offer", "name", "price", "qty"]


class SellerOrderSerializer(serializers.ModelSerializer):
    seller = serializers.SlugRelatedField(read_only=True, slug_field="username")
    items = SellerOrderItemSerializer(many=True, read_only=True)
    shipments = ShipmentSerializer(many=True, read_only=True)
    status = serializers.ChoiceField(
        choices=SellerOrder.Status.choices,
        read_only=True,
        help_text="Статус seller order: new, accepted, picking, shipped, delivered, canceled",
    )

    class Meta:
        model = SellerOrder
        fields = [
            "id", "seller", "seller_store_name", "status", "customer_comment", "internal_comment",
            "subtotal", "discount_amount", "total", "accepted_at", "shipped_at", "delivered_at",
            "items", "shipments",
        ]

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product","name","price","qty"]

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Order response",
            value={
                "id": 42,
                "legal_entity": 7,
                "placed_by": 3,
                "delivery_address": 14,
                "status": "new",
                "split_status": "planned",
                "approval_status": "pending",
                "requested_by": 3,
                "approved_by": None,
                "approved_at": None,
                "customer_comment": "Нужна утренняя доставка",
                "coupon_code": "WELCOME10",
                "source_channel": "api",
                "subtotal": "2590.00",
                "discount_amount": "259.00",
                "total": "2331.00",
                "created_at": "2026-03-11T14:00:00Z",
                "updated_at": "2026-03-11T14:00:01Z",
                "items": [{"product": 101, "name": "Бокал", "price": "790.00", "qty": 2}],
                "seller_splits": [{"seller": "horeca_manager", "seller_store_name": "Complaex Store", "items_count": 2, "subtotal": "2331.00", "status": "planned"}],
                "seller_orders": [],
            },
            response_only=True,
        )
    ]
)
class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    seller_splits = OrderSellerSplitSerializer(many=True, read_only=True)
    seller_orders = SellerOrderSerializer(many=True, read_only=True)
    status = serializers.ChoiceField(
        choices=Order.Status.choices,
        read_only=True,
        help_text="Жизненный цикл заказа: new, confirmed, paid, delivering, delivered, canceled, changed",
    )
    split_status = serializers.ChoiceField(
        choices=Order.SplitStatus.choices,
        read_only=True,
        help_text="Стадия распределения заказа между продавцами: single, planned, ready, split",
    )
    approval_status = serializers.ChoiceField(
        choices=Order.ApprovalStatus.choices,
        read_only=True,
        help_text="Стадия согласования заказа: not_required, pending, approved, rejected",
    )
    source_channel = serializers.ChoiceField(
        choices=Order.SourceChannel.choices,
        read_only=True,
        help_text="Канал создания заказа: web, twa, api",
    )

    class Meta:
        model = Order
        fields = [
            "id","legal_entity","placed_by","delivery_address","status","split_status",
            "approval_status","requested_by","approved_by","approved_at",
            "customer_comment","coupon_code","source_channel",
            "subtotal","discount_amount","total","created_at","updated_at","items","seller_splits","seller_orders"
        ]
        read_only_fields = ["placed_by","status","split_status","approval_status","requested_by","approved_by","approved_at","subtotal","discount_amount","total","created_at","updated_at"]

@extend_schema_serializer(
    examples=[
        OpenApiExample(
            "Create order",
            value={
                "legal_entity_id": 7,
                "delivery_address_id": 14,
                "items": [{"product_id": 101, "qty": 2}, {"product_id": 205, "qty": 1}],
                "customer_comment": "Нужна утренняя доставка",
                "coupon_code": "WELCOME10",
            },
            request_only=True,
        )
    ]
)
class OrderCreateSerializer(serializers.Serializer):
    legal_entity_id = serializers.IntegerField(help_text="ID юрлица, от имени которого создаётся заказ")
    delivery_address_id = serializers.IntegerField(help_text="ID адреса доставки, принадлежащего юрлицу")
    items = OrderItemInCreateSerializer(many=True, help_text="Позиции заказа")
    customer_comment = serializers.CharField(required=False, allow_blank=True, help_text="Комментарий клиента к заказу")
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=64, help_text="Промокод или купон")

    def validate(self, attrs):
        user = self.context["request"].user
        le_id = attrs["legal_entity_id"]
        addr_id = attrs["delivery_address_id"]
        if not LegalEntityMembership.objects.filter(user=user, legal_entity_id=le_id).exists():
            raise serializers.ValidationError("Нет доступа к выбранному юрлицу.")
        try:
            DeliveryAddress.objects.get(pk=addr_id, legal_entity_id=le_id)
        except DeliveryAddress.DoesNotExist:
            raise serializers.ValidationError("Адрес не принадлежит юрлицу.")
        prod_ids = [i["product_id"] for i in attrs["items"]]
        products = _resolve_products_map(prod_ids)
        if len(products) != len(set(prod_ids)):
            raise serializers.ValidationError("Некоторые товары не найдены.")
        attrs["__products"] = products
        attrs["__resolved_lines"] = _resolve_order_lines(attrs["items"], products)
        return attrs

    def create(self, validated_data):
        from .models import Order, OrderItem
        user = self.context["request"].user
        le_id = validated_data["legal_entity_id"]
        addr_id = validated_data["delivery_address_id"]
        lines = validated_data["__resolved_lines"]
        with transaction.atomic():
            discount_result = resolve_checkout_discount(
                user=user,
                customer_type=Order.CustomerType.COMPANY,
                coupon_code=validated_data.get("coupon_code", ""),
                guest_email="",
                lines=lines,
                lock=True,
            )
            if discount_result.error:
                raise serializers.ValidationError(discount_result.error)
            order = Order.objects.create(
                legal_entity_id=le_id,
                placed_by=user,
                requested_by=user,
                delivery_address_id=addr_id,
                customer_comment=validated_data.get("customer_comment", ""),
                coupon_code=discount_result.coupon.code if discount_result.coupon else "",
                source_channel=Order.SourceChannel.API,
            )
            items = []
            for line in lines:
                product = line["product"]
                items.append(
                    OrderItem(
                        order=order,
                        product=product,
                        seller_offer=line["offer"],
                        name=product.name,
                        price=line["price"],
                        qty=line["qty"],
                    )
                )
            OrderItem.objects.bulk_create(items)
            order.recalc_totals(explicit_discount_amount=discount_result.total_discount_amount)
            approval = resolve_order_approval_requirement(
                legal_entity=order.legal_entity,
                user=user,
                order_total=order.total,
            )
            order.approval_status = (
                Order.ApprovalStatus.PENDING if approval.requires_approval else Order.ApprovalStatus.APPROVED
            )
            order.save(update_fields=["subtotal","discount_amount","total","approval_status"])
            plan_seller_splits(order)
            create_redemption(order=order, discount_result=discount_result, user=user, guest_email="")
            return order
