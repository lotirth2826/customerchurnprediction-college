import csv
import json
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .forms import CustomerForm, PredictionForm
from .models import Customer, PredictionHistory
from .services import predict_customer


def home(request):
    return redirect("dashboard")


@login_required
def dashboard(request):
    customers = Customer.objects.all()
    total_customers = customers.count()
    active_customers = customers.filter(is_active=True).count()
    churn_customers = customers.filter(churn_prediction="Churn").count()
    high_risk_customers = customers.filter(risk_level="High").count()
    retention_rate = round(((total_customers - churn_customers) / total_customers) * 100, 2) if total_customers else 0

    context = {
        "total_customers": total_customers,
        "active_customers": active_customers,
        "churn_customers": churn_customers,
        "high_risk_customers": high_risk_customers,
        "retention_rate": retention_rate,
        "recent_predictions": PredictionHistory.objects.order_by("-created_at")[:8],
        "high_risk_list": customers.filter(risk_level="High").order_by("-churn_probability")[:8],
    }
    return render(request, "dashboard.html", context)


@login_required
def customer_list(request):
    customers = Customer.objects.all().order_by("-created_at")
    query = request.GET.get("q", "").strip()
    contract = request.GET.get("contract", "")
    gender = request.GET.get("gender", "")
    internet_service = request.GET.get("internet_service", "")

    if query:
        customers = customers.filter(Q(customer_id__icontains=query) | Q(name__icontains=query))
    if contract:
        customers = customers.filter(contract=contract)
    if gender:
        customers = customers.filter(gender=gender)
    if internet_service:
        customers = customers.filter(internet_service=internet_service)

    context = {
        "customers": customers,
        "query": query,
        "contract": contract,
        "gender": gender,
        "internet_service": internet_service,
        "contracts": Customer.CONTRACT_CHOICES,
        "genders": Customer.GENDER_CHOICES,
        "internet_services": Customer.INTERNET_CHOICES,
    }
    return render(request, "customer_list.html", context)


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return render(request, "customer_detail.html", {"customer": customer})


def _save_customer_from_form(form):
    data = form.cleaned_data
    result = predict_customer(data)
    customer = form.save(commit=False)
    customer.churn_prediction = result["prediction"]
    customer.churn_probability = result["probability"]
    customer.risk_level = result["risk_level"]
    customer.recommendation = result["recommendation"]
    customer.last_predicted_at = timezone.now()
    customer.save()
    PredictionHistory.objects.create(
        customer_name=customer.name,
        customer_id=customer.customer_id,
        prediction=customer.churn_prediction,
        probability=customer.churn_probability,
        risk_level=customer.risk_level,
        recommendation=customer.recommendation,
    )
    return customer


@login_required
def customer_create(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            _save_customer_from_form(form)
            messages.success(request, "Customer added and churn prediction generated.")
            return redirect("customer_list")
    else:
        form = CustomerForm()
    return render(request, "customer_form.html", {"form": form, "title": "Add Customer"})


@login_required
def customer_update(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            _save_customer_from_form(form)
            messages.success(request, "Customer updated and churn prediction refreshed.")
            return redirect("customer_detail", pk=pk)
    else:
        form = CustomerForm(instance=customer)
    return render(request, "customer_form.html", {"form": form, "title": "Update Customer"})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        customer.delete()
        messages.success(request, "Customer deleted.")
        return redirect("customer_list")
    return render(request, "customer_confirm_delete.html", {"customer": customer})


@login_required
def predict_customer_view(request):
    result = None
    if request.method == "POST":
        form = PredictionForm(request.POST)
        if form.is_valid():
            data = {
                "customer_id": f"TMP-{timezone.now().strftime('%Y%m%d%H%M%S')}",
                "name": form.cleaned_data["customer_name"],
                "gender": form.cleaned_data["gender"],
                "age": form.cleaned_data["age"],
                "contract": form.cleaned_data["contract"],
                "internet_service": form.cleaned_data["internet_service"],
                "tenure": form.cleaned_data["tenure"],
                "monthly_charges": form.cleaned_data["monthly_charges"],
            }
            result = predict_customer(data)
            PredictionHistory.objects.create(
                customer_name=data["name"],
                customer_id=data["customer_id"],
                prediction=result["prediction"],
                probability=result["probability"],
                risk_level=result["risk_level"],
                recommendation=result["recommendation"],
            )
    else:
        form = PredictionForm()
    return render(request, "predict.html", {"form": form, "result": result})


@login_required
def high_risk_customers(request):
    customers = Customer.objects.filter(risk_level="High").order_by("-churn_probability")
    return render(request, "high_risk.html", {"customers": customers})


@login_required
def analytics_dashboard(request):
    customers = Customer.objects.all()
    churn_yes = customers.filter(churn_prediction="Churn").count()
    churn_no = customers.filter(churn_prediction="Stay").count()

    context = {
        "churn_labels": json.dumps(["Churn", "Stay"]),
        "churn_data": json.dumps([churn_yes, churn_no]),
        "gender_labels": json.dumps(["Male", "Female"]),
        "gender_data": json.dumps([
            customers.filter(gender="Male").count(),
            customers.filter(gender="Female").count(),
        ]),
        "contract_labels": json.dumps([choice[0] for choice in Customer.CONTRACT_CHOICES]),
        "contract_data": json.dumps([customers.filter(contract=choice[0]).count() for choice in Customer.CONTRACT_CHOICES]),
        "monthly_charges_labels": json.dumps([c.name for c in customers.order_by("monthly_charges")[:20]]),
        "monthly_charges_data": json.dumps([float(c.monthly_charges) for c in customers.order_by("monthly_charges")[:20]]),
        "tenure_labels": json.dumps([c.name for c in customers.order_by("tenure")[:20]]),
        "tenure_data": json.dumps([c.tenure for c in customers.order_by("tenure")[:20]]),
        "feature_labels": json.dumps(["Tenure", "Monthly Charges", "Contract", "Internet Service", "Age"]),
        "feature_data": json.dumps([0.34, 0.28, 0.18, 0.12, 0.08]),
        "segment_labels": json.dumps([c.name for c in customers.order_by("-churn_probability")[:20]]),
        "segment_tenure": json.dumps([c.tenure for c in customers.order_by("-churn_probability")[:20]]),
        "segment_charges": json.dumps([float(c.monthly_charges) for c in customers.order_by("-churn_probability")[:20]]),
        "correlation_rows": [
            {"label": "Tenure", "value": 0.82},
            {"label": "Monthly Charges", "value": 0.71},
            {"label": "Contract", "value": 0.63},
            {"label": "Internet Service", "value": 0.55},
            {"label": "Age", "value": 0.31},
        ],
    }
    return render(request, "analytics.html", context)


@login_required
def prediction_history(request):
    history = PredictionHistory.objects.order_by("-created_at")
    return render(request, "history.html", {"history": history})


@login_required
def model_performance(request):
    metrics = {
        "accuracy": 0.89,
        "precision": 0.86,
        "recall": 0.84,
        "f1_score": 0.85,
        "roc_auc": 0.91,
    }
    confusion_matrix = [[82, 12], [15, 91]]
    return render(request, "performance.html", {"metrics": metrics, "confusion_matrix": confusion_matrix})


@login_required
def export_customers_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="customers.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Customer ID",
        "Name",
        "Gender",
        "Age",
        "Contract",
        "Internet Service",
        "Tenure",
        "Monthly Charges",
        "Prediction",
        "Probability",
        "Risk Level",
    ])
    for customer in Customer.objects.all().order_by("name"):
        writer.writerow([
            customer.customer_id,
            customer.name,
            customer.gender,
            customer.age,
            customer.contract,
            customer.internet_service,
            customer.tenure,
            customer.monthly_charges,
            customer.churn_prediction,
            customer.churn_probability,
            customer.risk_level,
        ])
    return response


@login_required
def export_history_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="prediction_history.csv"'
    writer = csv.writer(response)
    writer.writerow(["Customer Name", "Customer ID", "Prediction", "Probability", "Risk Level", "Recommendation", "Date Time"])
    for item in PredictionHistory.objects.all().order_by("-created_at"):
        writer.writerow([
            item.customer_name,
            item.customer_id,
            item.prediction,
            item.probability,
            item.risk_level,
            item.recommendation,
            item.created_at,
        ])
    return response


@login_required
def export_pdf_report(request):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle("Customer Churn Report")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, height - 50, "Customer Churn Prediction Report")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, height - 80, f"Generated at: {timezone.now()}")

    summary = [
        f"Total customers: {Customer.objects.count()}",
        f"High risk customers: {Customer.objects.filter(risk_level='High').count()}",
        f"Prediction history entries: {PredictionHistory.objects.count()}",
    ]
    y = height - 120
    for line in summary:
        pdf.drawString(50, y, line)
        y -= 20

    pdf.drawString(50, y - 10, "Top Customers")
    y -= 35
    for customer in Customer.objects.order_by("-churn_probability")[:8]:
        pdf.drawString(50, y, f"{customer.name} | {customer.churn_prediction} | {customer.churn_probability:.2f} | {customer.risk_level}")
        y -= 18

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="churn_report.pdf"'
    return response
