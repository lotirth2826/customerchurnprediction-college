from django.contrib import admin

from .models import Customer, PredictionHistory


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "customer_id",
        "name",
        "gender",
        "contract",
        "internet_service",
        "tenure",
        "monthly_charges",
        "churn_prediction",
        "churn_probability",
        "risk_level",
        "is_active",
    )
    search_fields = ("customer_id", "name")
    list_filter = ("gender", "contract", "internet_service", "risk_level", "is_active")


@admin.register(PredictionHistory)
class PredictionHistoryAdmin(admin.ModelAdmin):
    list_display = ("customer_name", "prediction", "probability", "risk_level", "created_at")
    search_fields = ("customer_name", "customer_id")
