from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('coupon/apply/', views.coupon_apply, name='coupon_apply'),
    path('coupon/remove/', views.coupon_remove, name='coupon_remove'),
    # Above `<int:order_id>/` — that pattern only matches digits, so 'track'
    # would not collide, but keeping the specific routes first is the habit
    # that stops the next addition from breaking.
    path('track/', views.track, name='track'),
    path('track/api/', views.track_api, name='track_api'),

    path('', views.order_history, name='history'),
    path('<int:order_id>/', views.order_detail, name='detail'),
]
