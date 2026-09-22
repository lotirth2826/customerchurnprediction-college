from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Customer, PredictionHistory, RetentionAction


class PredictionHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="history-test-user", password="safe-test-password"
        )
        self.customer = Customer.objects.create(
            customer_id="HISTORY-TEST-001",
            name="Test Customer",
            gender="Male",
            age=30,
            contract="Month-to-month",
            internet_service="DSL",
            tenure=6,
            monthly_charges=50,
        )
        self.history_item = PredictionHistory.objects.create(
            customer_name="Test Customer",
            customer_id=self.customer.customer_id,
            prediction="Stay",
            probability=0.2,
            risk_level="Low",
        )
        self.client.force_login(self.user)

    def test_history_page_loads(self):
        response = self.client.get(reverse("history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Customer")

    def test_delete_removes_customer_and_related_history(self):
        response = self.client.post(reverse("history"), {"delete_id": self.history_item.pk})
        self.assertRedirects(response, reverse("history"))
        self.assertFalse(PredictionHistory.objects.filter(pk=self.history_item.pk).exists())
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())

        analytics_response = self.client.get(reverse("analytics"))
        self.assertEqual(analytics_response.context["gender_data"], "[0, 0]")

    def test_high_risk_history_can_receive_retention_action(self):
        high_risk_item = PredictionHistory.objects.create(
            customer_name="At Risk Customer",
            customer_id="HIGH-RISK-001",
            prediction="Churn",
            probability=0.85,
            risk_level="High",
        )
        response = self.client.post(
            reverse("retention_action_add", args=[high_risk_item.pk]),
            {"action_type": "Contact", "status": "In Progress", "notes": "Called the customer."},
        )
        self.assertRedirects(response, reverse("retention_tracker"))
        self.assertTrue(
            RetentionAction.objects.filter(prediction_history=high_risk_item, action_type="Contact").exists()
        )
        tracker_response = self.client.get(reverse("retention_tracker"))
        self.assertContains(tracker_response, "At Risk Customer")
        self.assertContains(tracker_response, "Contact")

    def test_tracker_displays_all_prediction_history(self):
        response = self.client.get(reverse("retention_tracker"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Customer")
        self.assertContains(response, "Low")

    def test_retention_action_can_be_updated(self):
        high_risk_item = PredictionHistory.objects.create(
            customer_name="At Risk Customer",
            customer_id="HIGH-RISK-UPDATE-001",
            prediction="Churn",
            probability=0.85,
            risk_level="High",
        )
        action = RetentionAction.objects.create(
            prediction_history=high_risk_item,
            action_type="Contact",
            status="Planned",
            notes="Initial outreach planned.",
        )

        response = self.client.post(
            reverse("retention_action_edit", args=[action.pk]),
            {"action_type": "Discount", "status": "Completed", "notes": "Discount accepted."},
        )

        self.assertRedirects(response, reverse("retention_tracker"))
        action.refresh_from_db()
        self.assertEqual(action.action_type, "Discount")
        self.assertEqual(action.status, "Completed")
        self.assertEqual(action.notes, "Discount accepted.")
