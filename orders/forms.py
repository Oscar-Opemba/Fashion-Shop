from django import forms
from django.utils import timezone

from .models import Coupon, Order


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'full_name', 'phone', 'email',
            'county', 'town', 'street', 'notes',
        ]
        widgets = {
            'full_name': forms.TextInput(
                attrs={'placeholder': 'Full name', 'autocomplete': 'name'}
            ),
            # inputmode/type together are what make phones show a number pad.
            'phone': forms.TextInput(attrs={
                'placeholder': '07XX XXX XXX',
                'type': 'tel',
                'inputmode': 'numeric',
                'autocomplete': 'tel',
            }),
            'email': forms.EmailInput(
                attrs={'placeholder': 'Email (optional)', 'autocomplete': 'email'}
            ),
            'county': forms.TextInput(
                attrs={'placeholder': 'County', 'autocomplete': 'address-level1'}
            ),
            'town': forms.TextInput(
                attrs={'placeholder': 'Town', 'autocomplete': 'address-level2'}
            ),
            'street': forms.TextInput(attrs={
                'placeholder': 'Street / estate / building',
                'autocomplete': 'street-address',
            }),
            'notes': forms.Textarea(
                attrs={'placeholder': 'Delivery notes (optional)', 'rows': 3}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')
            if name != 'notes':
                field.widget.attrs.setdefault('aria-label', field.label)

    def clean_phone(self):
        from payments.daraja import normalise_phone

        phone = normalise_phone(self.cleaned_data['phone'])
        if phone is None:
            raise forms.ValidationError(
                'Enter a valid Safaricom number, e.g. 0712345678.'
            )
        return phone


class CouponApplyForm(forms.Form):
    code = forms.CharField(
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Coupon code'}
        )
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        now = timezone.now()
        try:
            self.coupon = Coupon.objects.get(
                code__iexact=code, active=True,
                valid_from__lte=now, valid_to__gte=now,
            )
        except Coupon.DoesNotExist:
            raise forms.ValidationError('That coupon is not valid.')
        return code
