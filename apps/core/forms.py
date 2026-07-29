from django import forms
from django.core.exceptions import ValidationError
import re

from .models import Booking


class BookingForm(forms.ModelForm):
    """Форма для создания записи на услугу"""

    class Meta:
        model = Booking
        fields = [
            'salon', 'procedure', 'specialist',
            'customer_name', 'phone', 'question'
        ]
        widgets = {
            'salon': forms.HiddenInput(),
            'procedure': forms.HiddenInput(),
            'specialist': forms.HiddenInput(),
            'question': forms.Textarea(attrs={
                'class': 'contacts__form_textarea',
                'placeholder': 'Вопрос (необязательно)',
                'rows': 3
            }),
        }
        labels = {
            'customer_name': 'Ваше имя',
            'phone': 'Телефон',
            'question': 'Комментарий',
        }

    customer_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'contacts__form_iunput',
            'placeholder': 'Введите ваше имя',
            'required': True
        })
    )

    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'contacts__form_iunput',
            'placeholder': '+7 (999) 999-99-99',
            'required': True
        })
    )

    booking_date = forms.DateField(
        required=False,
        widget=forms.HiddenInput()
    )

    booking_time = forms.TimeField(
        required=False,
        widget=forms.HiddenInput()
    )

    def clean_phone(self):
        """Очистка и приведение телефона к формату +79998887766"""
        phone = self.cleaned_data.get('phone', '').strip()

        phone = ''.join(c for c in phone if c.isdigit() or c == '+')

        if phone.startswith('8'):
            phone = '+7' + phone[1:]
        elif phone.startswith('7'):
            phone = '+7' + phone[1:]
        elif not phone.startswith('+7'):
            phone = '+7' + phone.lstrip('+7')

        if not re.fullmatch(r'^\+7\d{10}$', phone):
            raise ValidationError('Телефон должен быть в формате: +79998887766')

        return phone