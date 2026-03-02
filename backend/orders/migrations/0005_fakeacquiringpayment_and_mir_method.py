from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_statuses_update"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("cash", "Наличные"),
                    ("invoice", "По счёту"),
                    ("mir_card", "Карта МИР"),
                ],
                default="cash",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="FakeAcquiringPayment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=12)),
                ("provider_payment_id", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "Создан"),
                            ("processing", "В обработке"),
                            ("requires_3ds", "Требуется 3DS"),
                            ("paid", "Оплачен"),
                            ("failed", "Ошибка"),
                            ("canceled", "Отменен"),
                            ("refunded", "Возврат"),
                        ],
                        default="created",
                        max_length=24,
                    ),
                ),
                (
                    "last_event",
                    models.CharField(
                        choices=[
                            ("start", "Инициация"),
                            ("success", "Успешная оплата"),
                            ("fail", "Ошибка оплаты"),
                            ("cancel", "Отмена пользователем"),
                            ("require_3ds", "Запрос 3DS"),
                            ("pass_3ds", "3DS успешно"),
                            ("refund", "Возврат"),
                        ],
                        default="start",
                        max_length=24,
                    ),
                ),
                ("history", models.JSONField(blank=True, default=list)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="fake_payment", to="orders.order")),
            ],
        ),
    ]
