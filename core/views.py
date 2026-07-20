from django.shortcuts import render

from catalog.models import Category, Product


def home(request):
    return render(request, 'core/home.html', {
        'featured_products': Product.objects.filter(
            is_active=True
        ).select_related('category')[:8],
        'categories': Category.objects.all()[:3],
    })


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')
