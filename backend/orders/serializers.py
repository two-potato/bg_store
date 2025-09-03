from rest_framework import serializers
from .models import Order, OrderItem
from catalog.models import Product
from commerce.models import DeliveryAddress, LegalEntityMembership

class OrderItemInCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1)

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["product","name","price","qty"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = ["id","legal_entity","placed_by","delivery_address","status","subtotal","discount_amount","total","created_at","updated_at","items"]
        read_only_fields = ["placed_by","status","subtotal","discount_amount","total","created_at","updated_at"]

class OrderCreateSerializer(serializers.Serializer):
    legal_entity_id = serializers.IntegerField()
    delivery_address_id = serializers.IntegerField()
    items = OrderItemInCreateSerializer(many=True)

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
        products = {p.id: p for p in Product.objects.filter(id__in=prod_ids)}
        if len(products) != len(prod_ids):
            raise serializers.ValidationError("Некоторые товары не найдены.")
        attrs["__products"] = products
        return attrs

    def create(self, validated_data):
        from .models import Order, OrderItem
        user = self.context["request"].user
        le_id = validated_data["legal_entity_id"]
        addr_id = validated_data["delivery_address_id"]
        products = validated_data["__products"]
        order = Order.objects.create(legal_entity_id=le_id, placed_by=user, delivery_address_id=addr_id)
        items = []
        for item in validated_data["items"]:
            p = products[item["product_id"]]
            items.append(OrderItem(order=order, product=p, name=p.name, price=p.price, qty=item["qty"]))
        OrderItem.objects.bulk_create(items)
        order.recalc_totals()
        order.save(update_fields=["subtotal","discount_amount","total"])
        return order
