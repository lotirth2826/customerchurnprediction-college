import csv
import json
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .forms import CustomerForm, PredictionForm, RetentionActionForm
from .models import Customer, PredictionHistory, RetentionAction
from .services import model_performance as get_model_performance, predict_customer


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
    _create_prediction_history(customer, result)
    return customer


def _create_prediction_history(customer, result):
    """Store the complete input and output for every prediction."""
    return PredictionHistory.objects.create(
        customer_name=customer.name,
        customer_id=customer.customer_id,
        gender=customer.gender,
        age=customer.age,
        contract=customer.contract,
        internet_service=customer.internet_service,
        tenure=customer.tenure,
        monthly_charges=customer.monthly_charges,
        prediction=result["prediction"],
        probability=result["probability"],
        risk_level=result["risk_level"],
        prediction_factors=", ".join(result["factors"]),
        recommendation=result["recommendation"],
    )


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
                # Microseconds make each quick consecutive prediction distinct.
                "customer_id": f"PRED-{timezone.now().strftime('%Y%m%d%H%M%S%f')}",
                "name": form.cleaned_data["customer_name"],
                "gender": form.cleaned_data["gender"],
                "age": form.cleaned_data["age"],
                "contract": form.cleaned_data["contract"],
                "internet_service": form.cleaned_data["internet_service"],
                "tenure": form.cleaned_data["tenure"],
                "monthly_charges": form.cleaned_data["monthly_charges"],
            }
            result = predict_customer(data)
            with transaction.atomic():
                customer = Customer.objects.create(
                    customer_id=data["customer_id"],
                    name=data["name"],
                    gender=data["gender"],
                    age=data["age"],
                    contract=data["contract"],
                    internet_service=data["internet_service"],
                    tenure=data["tenure"],
                    monthly_charges=data["monthly_charges"],
                    churn_prediction=result["prediction"],
                    churn_probability=result["probability"],
                    risk_level=result["risk_level"],
                    recommendation=result["recommendation"],
                    last_predicted_at=timezone.now(),
                )
                _create_prediction_history(customer, result)
            messages.success(request, "Prediction saved to customer records and prediction history.")
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
    active_risk_segments = customers.exclude(risk_level="").values("risk_level").distinct().count()

    context = {
        "active_risk_segments": active_risk_segments,
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
    if request.method == "POST":
        item = get_object_or_404(PredictionHistory, pk=request.POST.get("delete_id"))
        customer_id = item.customer_id
        with transaction.atomic():
            # A history deletion is treated as deleting that customer from the
            # application, keeping Customers, History, and Analytics aligned.
            if customer_id:
                Customer.objects.filter(customer_id=customer_id).delete()
                PredictionHistory.objects.filter(customer_id=customer_id).delete()
            else:
                item.delete()
        messages.success(request, "Customer and related prediction history deleted.")
        return redirect("history")
    history = PredictionHistory.objects.order_by("-created_at")
    return render(request, "history.html", {"history": history})


@login_required
def retention_action_tracker(request):
    prediction_history = PredictionHistory.objects.prefetch_related(
        "retention_actions"
    ).order_by("-created_at")
    return render(request, "retention_tracker.html", {"prediction_history": prediction_history})


@login_required
def retention_action_create(request, history_pk):
    history_item = get_object_or_404(PredictionHistory, pk=history_pk)
    if request.method == "POST":
        form = RetentionActionForm(request.POST)
        if form.is_valid():
            action = form.save(commit=False)
            action.prediction_history = history_item
            action.save()
            messages.success(request, "Retention action recorded.")
            return redirect("retention_tracker")
    else:
        form = RetentionActionForm()
    return render(request, "retention_action_form.html", {"form": form, "history_item": history_item})


@login_required
def retention_action_update(request, pk):
    """Allow staff to keep an existing retention action current."""
    action = get_object_or_404(
        RetentionAction.objects.select_related("prediction_history"), pk=pk
    )
    if request.method == "POST":
        form = RetentionActionForm(request.POST, instance=action)
        if form.is_valid():
            form.save()
            messages.success(request, "Retention action updated.")
            return redirect("retention_tracker")
    else:
        form = RetentionActionForm(instance=action)
    return render(
        request,
        "retention_action_form.html",
        {
            "form": form,
            "history_item": action.prediction_history,
            "action": action,
        },
    )


@login_required
def model_performance(request):
    performance = get_model_performance().copy()
    confusion_matrix = performance.pop("confusion_matrix")
    return render(request, "performance.html", {"metrics": performance, "confusion_matrix": confusion_matrix})


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
    customers = Customer.objects.all().order_by("name")
    customer_ids = set(customers.values_list("customer_id", flat=True))
    for customer in customers:
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

    # Older Predict-form submissions were saved only in history.  Include them
    # too, so downloading the main CSV does not hide any prior predictions.
    for item in PredictionHistory.objects.exclude(customer_id__in=customer_ids).order_by("customer_name"):
        writer.writerow([
            item.customer_id,
            item.customer_name,
            item.gender,
            item.age,
            item.contract,
            item.internet_service,
            item.tenure,
            item.monthly_charges,
            item.prediction,
            item.probability,
            item.risk_level,
        ])
    return response


@login_required
def export_history_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="prediction_history.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Customer Name", "Gender", "Age", "Contract", "Internet Service",
        "Tenure", "Monthly Charges", "Prediction Factors", "Prediction",
        "Probability", "Risk Level", "Recommendation", "Date Time",
    ])
    for item in PredictionHistory.objects.all().order_by("-created_at"):
        writer.writerow([
            item.customer_name,
            item.gender,
            item.age,
            item.contract,
            item.internet_service,
            item.tenure,
            item.monthly_charges,
            item.prediction_factors,
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
