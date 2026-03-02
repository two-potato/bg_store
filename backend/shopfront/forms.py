from django import forms


class ContactFeedbackForm(forms.Form):
    name = forms.CharField(max_length=120, label="Имя")
    phone = forms.CharField(max_length=32, label="Телефон")
    message = forms.CharField(
        label="Сообщение",
        widget=forms.Textarea(attrs={"rows": 5}),
        max_length=2000,
    )

