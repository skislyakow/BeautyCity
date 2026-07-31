from django.urls import path
from apps.core import views, phone_auth

urlpatterns = [
    path('', views.index, name='index'),
    path('service/', views.service, name='service'),
    path('service-finally/', views.service_finally, name='service_finally'),
    path('notes/', views.notes, name='notes'),
    path('dashboard/', views.admin_panel, name='admin'),

    # Авторизация по телефону (SMS-код заглушка 1234)
    path('phone-login/', phone_auth.phone_login_view, name='phone_login'),
    path('phone-confirm/', phone_auth.phone_confirm_view, name='phone_confirm'),
    path('logout/', phone_auth.logout_view, name='logout'),

    # API
    path('api/salons/', views.salon_list, name='api_salons'),
    path('api/procedures/', views.procedure_list, name='api_procedures'),
    path('api/specialists/', views.specialist_list, name='api_specialists'),
    path('api/procedure-offerings/', views.procedure_offering_list, name='api_offerings'),
    path('api/salons/<int:pk>/procedures/', views.salon_procedures, name='api_salon_procedures'),
    path('api/salons/<int:pk>/specialists/', views.salon_specialists, name='api_salon_specialists'),
    path('api/specialists/<int:pk>/procedures/', views.specialist_procedures, name='api_specialist_procedures'),
    path('api/specialists/<int:pk>/salons/', views.specialist_salons, name='api_specialist_salons'),
    path('api/slots/', views.available_slots, name='api_slots'),
    path('api/bookings/', views.create_booking, name='api_create_booking'),
    path('api/my-bookings/', views.my_bookings, name='api_my_bookings'),
    path('api/payments/<int:booking_id>/', views.initiate_payment, name='api_payment'),
    path('api/admin/stats/', views.admin_stats, name='api_admin_stats'),
]