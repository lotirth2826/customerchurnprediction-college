from django.db import models


class Customer(models.Model):
    GENDER_CHOICES = [("Male", "Male"), ("Female", "Female")]
    CONTRACT_CHOICES = [
        ("Month-to-month", "Month-to-month"),
        ("One year", "One year"),
        ("Two year", "Two year"),
    ]
    INTERNET_CHOICES = [
        ("DSL", "DSL"),
        ("Fiber optic", "Fiber optic"),
        ("No", "No"),
    ]
    PREDICTION_CHOICES = [("Stay", "Stay"), ("Churn", "Churn")]
    RISK_CHOICES = [("Low", "Low"), ("Medium", "Medium"), ("High", "High")]

    customer_id = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=120)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    age = models.PositiveIntegerField()
    contract = models.CharField(max_length=30, choices=CONTRACT_CHOICES)
    internet_service = models.CharField(max_length=20, choices=INTERNET_CHOICES)
    tenure = models.PositiveIntegerField()
    monthly_charges = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    churn_prediction = models.CharField(max_length=10, choices=PREDICTION_CHOICES, blank=True)
    churn_probability = models.FloatField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, blank=True)
    recommendation = models.TextField(blank=True)
    last_predicted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer_id} - {self.name}"


class PredictionHistory(models.Model):
    PREDICTION_CHOICES = [("Stay", "Stay"), ("Churn", "Churn")]

    customer_name = models.CharField(max_length=120)
    customer_id = models.CharField(max_length=30, blank=True)
    prediction = models.CharField(max_length=10, choices=PREDICTION_CHOICES)
    probability = models.FloatField()
    risk_level = models.CharField(max_length=10)
    recommendation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.prediction}"
