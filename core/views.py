from django.db.models import Avg
from django.shortcuts import render

from catalog.models import Category, Product


def home(request):
    return render(request, 'core/home.html', {
        'featured_products': Product.objects.filter(
            is_active=True
        ).select_related('category').annotate(
            avg_rating=Avg('reviews__rating')
        )[:8],
        # The banner takes the first three; the filter tabs need them all.
        'categories': Category.objects.all(),
    })


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    return render(request, 'core/contact.html')
