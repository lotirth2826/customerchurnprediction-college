from math import fsum


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


def churn_probability_for_customer(customer_data):
    monthly = float(customer_data["monthly_charges"])
    tenure = int(customer_data["tenure"])
    age = int(customer_data["age"])
    contract = customer_data["contract"]
    internet_service = customer_data["internet_service"]

    score_parts = [
        0.12,
        min(monthly / 250, 0.35),
        0.3 if tenure < 12 else 0.12 if tenure < 36 else 0.03,
        0.12 if contract == "Month-to-month" else 0.05 if contract == "One year" else 0.0,
        0.12 if internet_service == "Fiber optic" else 0.04 if internet_service == "DSL" else 0.0,
        0.04 if age > 60 else 0.0,
    ]
    return min(round(fsum(score_parts), 2), 0.99)


def predict_customer(customer_data):
    probability = churn_probability_for_customer(customer_data)
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
    }
