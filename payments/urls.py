from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('start/<int:order_id>/', views.start, name='start'),
    path('waiting/<int:order_id>/', views.waiting, name='waiting'),
    path('status/<int:order_id>/', views.status, name='status'),
    path('success/<int:order_id>/', views.success, name='success'),
    path('failed/<int:order_id>/', views.failed, name='failed'),
    path('retry/<int:order_id>/', views.retry, name='retry'),

    # Unauthenticated endpoint Safaricom posts to; the token segment is what
    # keeps the url from being guessable.
    path('callback/<str:token>/', views.callback, name='callback'),
]
