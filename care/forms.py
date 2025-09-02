from django import forms
from .models import Patient, CareRecord

class DateInput(forms.DateInput):
    input_type = 'date'

class TimeInput(forms.TimeInput):
    input_type = 'time'

class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["name", "birth_date", "notes"]
        widgets = {
            "birth_date": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3})
        }

class CareRecordForm(forms.ModelForm):
    class Meta:
        model = CareRecord
        fields = ["patient", "type", "time", "what", "description", "caregiver", "date"]
        widgets = {
            "date": DateInput(),
            "time": TimeInput(),
            "description": forms.Textarea(attrs={"rows": 2}),
        }
