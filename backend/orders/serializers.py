from rest_framework import serializers
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

class OrderItemInCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)


class OrderSellerSplitSerializer(serializers.ModelSerializer):
    seller = serializers.SlugRelatedField(read_only=True, slug_field="username")

    class Meta:
        model = OrderSellerSplit
        fields = ["seller", "seller_store_name", "items_count", "subtotal", "status"]


class ShipmentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentItem
        fields = ["seller_order_item", "qty"]


class ShipmentSerializer(serializers.ModelSerializer):
    items = ShipmentItemSerializer(many=True, read_only=True)

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

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    seller_splits = OrderSellerSplitSerializer(many=True, read_only=True)
    seller_orders = SellerOrderSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = [
            "id","legal_entity","placed_by","delivery_address","status","split_status",
            "approval_status","requested_by","approved_by","approved_at",
            "customer_comment","coupon_code","source_channel",
            "subtotal","discount_amount","total","created_at","updated_at","items","seller_splits","seller_orders"
        ]
        read_only_fields = ["placed_by","status","split_status","approval_status","requested_by","approved_by","approved_at","subtotal","discount_amount","total","created_at","updated_at"]

class OrderCreateSerializer(serializers.Serializer):
    legal_entity_id = serializers.IntegerField()
    delivery_address_id = serializers.IntegerField()
    items = OrderItemInCreateSerializer(many=True)
    customer_comment = serializers.CharField(required=False, allow_blank=True)
    coupon_code = serializers.CharField(required=False, allow_blank=True, max_length=64)

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
