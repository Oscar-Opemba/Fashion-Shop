from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.product_list, name='product_list'),

    # Staff CRUD. These MUST stay above `<slug:slug>/` — Django matches
    # top-down and that pattern is a catch-all under /shop/, so 'manage'
    # would otherwise be read as a product slug and 404.
    path('manage/', views.ProductManageList.as_view(), name='manage_list'),
    path('manage/new/', views.ProductCreateView.as_view(), name='product_create'),
    path(
        'manage/<slug:slug>/edit/',
        views.ProductUpdateView.as_view(),
        name='product_update',
    ),
    path(
        'manage/<slug:slug>/delete/',
        views.ProductDeleteView.as_view(),
        name='product_delete',
    ),
    path(
        'manage-category/new/',
        views.CategoryCreateView.as_view(),
        name='category_create',
    ),
    path(
        'manage-category/<slug:slug>/edit/',
        views.CategoryUpdateView.as_view(),
        name='category_update',
    ),
    path(
        'manage-category/<slug:slug>/delete/',
        views.CategoryDeleteView.as_view(),
        name='category_delete',
    ),

    path('<slug:slug>/', views.product_detail, name='product_detail'),
]
