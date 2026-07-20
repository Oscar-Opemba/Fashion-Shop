from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('<slug:slug>/', views.product_detail, name='product_detail'),
    path('<slug:slug>/review/', views.review_add, name='review_add'),
    path('<slug:slug>/wishlist/', views.wishlist_toggle, name='wishlist_toggle'),
]
