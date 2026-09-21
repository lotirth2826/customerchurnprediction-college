from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/add/", views.customer_create, name="customer_add"),
    path("customers/<int:pk>/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_update, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    path("predict/", views.predict_customer_view, name="predict"),
    path("high-risk/", views.high_risk_customers, name="high_risk"),
    path("analytics/", views.analytics_dashboard, name="analytics"),
    path("history/", views.prediction_history, name="history"),
    path("retention-actions/", views.retention_action_tracker, name="retention_tracker"),
    path("retention-actions/<int:history_pk>/add/", views.retention_action_create, name="retention_action_add"),
    path("performance/", views.model_performance, name="performance"),
    path("reports/customers.csv", views.export_customers_csv, name="export_customers_csv"),
    path("reports/history.csv", views.export_history_csv, name="export_history_csv"),
    path("reports/report.pdf", views.export_pdf_report, name="export_pdf_report"),
]
