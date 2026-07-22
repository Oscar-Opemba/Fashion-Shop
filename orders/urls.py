from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('placed/<int:order_id>/', views.order_placed, name='placed'),
    path('coupon/apply/', views.coupon_apply, name='coupon_apply'),
    path('coupon/remove/', views.coupon_remove, name='coupon_remove'),
    path('', views.order_history, name='history'),
    path('<int:order_id>/', views.order_detail, name='detail'),
]
