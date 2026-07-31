from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.models import User
from .models import CustomerProfile
import random

def phone_login_view(request):
   if request.method == 'POST':
        phone = request.POST.get('tel')
        testing_code = '1234'
        request.session['auth_phone'] = phone
        request.session['auth_code'] = testing_code
        messages.success(request, 'Введите код из СМС')
        return render(request, 'index.html')

def phone_confirm_view(request):
    if request.method == 'POST':
        num1 = request.POST.get('num1')
        num2 = request.POST.get('num2')
        num3 = request.POST.get('num3')
        num4 = request.POST.get('num4')

        code = num1 + num2 + num3 + num4
        auth_code = request.session.get('auth_code')
        auth_phone = request.session.get('auth_phone')
        if auth_code == code:
            user, created = User.objects.get_or_create(username=auth_phone)
            if created == True:
                CustomerProfile.objects.create(user=user, phone=auth_phone)
            login(request,user)
            messages.success(request, 'Вход успешно выполнен')
            del request.session['auth_phone']
            del request.session['auth_code']
            return redirect('index')
        else:
            messages.error(request, 'Введен неверный код')
            return redirect('index')
