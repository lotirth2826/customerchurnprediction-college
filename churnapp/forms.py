from django import forms

from .models import Customer


class BootstrapMixin:
    def add_bootstrap(self):
        for field in self.fields.values():
            css = "form-control"
            if isinstance(field.widget, forms.Select):
                css = "form-select"
            field.widget.attrs["class"] = css


class CustomerForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "customer_id",
            "name",
            "gender",
            "age",
            "contract",
            "internet_service",
            "tenure",
            "monthly_charges",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap()


class PredictionForm(BootstrapMixin, forms.Form):
    customer_name = forms.CharField(max_length=120)
    gender = forms.ChoiceField(choices=Customer.GENDER_CHOICES)
    age = forms.IntegerField(min_value=10, max_value=100)
    contract = forms.ChoiceField(choices=Customer.CONTRACT_CHOICES)
    internet_service = forms.ChoiceField(choices=Customer.INTERNET_CHOICES)
    tenure = forms.IntegerField(min_value=0, max_value=130)
    monthly_charges = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_bootstrap()
