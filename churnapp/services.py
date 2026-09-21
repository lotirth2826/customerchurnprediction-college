"""Model training, prediction, and explanation helpers."""

from functools import lru_cache
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


DATASET_PATH = Path(__file__).resolve().parent.parent / "customer_churn_data.csv"
FEATURE_COLUMNS = [
    "Age", "Gender", "Tenure", "MonthlyCharges", "ContractType", "InternetService",
]
NUMERIC_FEATURES = ["Age", "Tenure", "MonthlyCharges"]
CATEGORICAL_FEATURES = ["Gender", "ContractType", "InternetService"]


def risk_level_from_probability(probability):
    if probability >= 0.7:
        return "High"
    if probability >= 0.4:
        return "Medium"
    return "Low"


def recommendation_for_customer(probability, contract, tenure):
    if probability >= 0.7:
        return "Offer discount, upgrade plan, and contact customer immediately."
    if contract == "Month-to-month" and tenure < 12:
        return "Offer a long-term contract discount and proactive support."
    if probability >= 0.4:
        return "Provide better support and review pricing options."
    return "Keep the customer engaged with loyalty benefits."


def _pipeline(classifier):
    return Pipeline([
        ("features", ColumnTransformer([
            ("numeric", "passthrough", NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ])),
        ("classifier", classifier),
    ])


@lru_cache(maxsize=1)
def _trained_model():
    """Choose the stronger tree ensemble on a reproducible validation split."""
    data = pd.read_csv(DATASET_PATH)
    features = data[FEATURE_COLUMNS]
    target = data["Churn"].eq("Yes").astype(int)
    train_x, validation_x, train_y, validation_y = train_test_split(
        features, target, test_size=0.20, random_state=42, stratify=target,
    )
    candidates = [
        _pipeline(ExtraTreesClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )),
        _pipeline(RandomForestClassifier(
            n_estimators=400, min_samples_leaf=2, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )),
    ]
    best_model = max(
        candidates,
        key=lambda model: accuracy_score(
            validation_y, model.fit(train_x, train_y).predict(validation_x)
        ),
    )
    validation_predictions = best_model.predict(validation_x)
    validation_probabilities = best_model.predict_proba(validation_x)[:, 1]
    metrics = _metrics(validation_y, validation_predictions, validation_probabilities)
    # Refit on all available labelled data after model selection.
    best_model.fit(features, target)
    return best_model, metrics


def _metrics(actual, predicted, probabilities):
    precision, recall, f1_score, _ = precision_recall_fscore_support(
        actual, predicted, average="binary", zero_division=0,
    )
    return {
        "accuracy": round(accuracy_score(actual, predicted) * 100, 2),
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1_score * 100, 2),
        "roc_auc": round(roc_auc_score(actual, probabilities) * 100, 2),
        "confusion_matrix": confusion_matrix(actual, predicted).tolist(),
    }


def model_performance():
    """Return hold-out validation metrics for the current dataset-trained model."""
    _, metrics = _trained_model()
    return metrics


def prediction_factors(customer_data):
    """Return the input conditions that most meaningfully influence this result."""
    factors = []
    if customer_data["contract"] == "Month-to-month":
        factors.append("Month-to-month contract")
    elif customer_data["contract"] == "Two year":
        factors.append("Two-year contract stability")
    if int(customer_data["tenure"]) < 12:
        factors.append("Short tenure (under 12 months)")
    elif int(customer_data["tenure"]) >= 36:
        factors.append("Long customer tenure")
    if customer_data["internet_service"] == "Fiber optic":
        factors.append("Fiber optic internet service")
    if float(customer_data["monthly_charges"]) >= 80:
        factors.append("High monthly charges")
    if int(customer_data["age"]) >= 60:
        factors.append("Senior customer age")
    return factors or ["Customer profile and service usage pattern"]


def predict_customer(customer_data):
    input_row = pd.DataFrame([{
        "Age": int(customer_data["age"]),
        "Gender": customer_data["gender"],
        "Tenure": int(customer_data["tenure"]),
        "MonthlyCharges": float(customer_data["monthly_charges"]),
        "ContractType": customer_data["contract"],
        "InternetService": customer_data["internet_service"],
    }])
    model, _ = _trained_model()
    probability = round(float(model.predict_proba(input_row)[0][1]), 2)
    prediction = "Churn" if probability >= 0.5 else "Stay"
    risk_level = risk_level_from_probability(probability)
    recommendation = recommendation_for_customer(
        probability,
        customer_data["contract"],
        customer_data["tenure"],
    )
    return {
        "prediction": prediction,
        "probability": probability,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "factors": prediction_factors(customer_data),
    }
