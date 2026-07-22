from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import Category, Product

PAGE_SIZE = 12

# The theme's sidebar filters price with a list of range links rather than a
# pair of inputs, so the bands are fixed. Values are KES.
PRICE_BANDS = [
    (None, 2000),
    (2000, 5000),
    (5000, 10000),
    (10000, 20000),
    (20000, None),
]


def price_band_links(request):
    """Build the sidebar's price links, keeping any other active filters."""
    links = []
    for low, high in PRICE_BANDS:
        params = request.GET.copy()
        for key in ('page', 'min_price', 'max_price'):
            params.pop(key, None)
        if low is not None:
            params['min_price'] = low
        if high is not None:
            params['max_price'] = high

        if low is None:
            label = f'Under KES {high:,}'
        elif high is None:
            label = f'KES {low:,}+'
        else:
            label = f'KES {low:,} - {high:,}'

        links.append({'label': label, 'query': params.urlencode()})
    return links


def product_list(request):
    products = Product.objects.filter(is_active=True).select_related('category')

    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    category_slug = request.GET.get('category', '').strip()
    active_category = None
    if category_slug:
        active_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=active_category)

    # Price bounds are optional and applied independently, so a shopper can set
    # just a ceiling without also having to pick a floor.
    for param, lookup in (('min_price', 'price__gte'), ('max_price', 'price__lte')):
        raw = request.GET.get(param, '').strip()
        if raw:
            try:
                products = products.filter(**{lookup: float(raw)})
            except ValueError:
                pass

    sort = request.GET.get('sort', '')
    products = products.order_by(
        {'price': 'price', '-price': '-price', 'name': 'name'}.get(sort, '-created')
    )

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get('page'))

    # Preserve the active filters when building pagination links.
    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'catalog/product_list.html', {
        'page_obj': page,
        'products': page.object_list,
        'categories': Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True))
        ),
        'active_category': active_category,
        'query': query,
        'sort': sort,
        'querystring': params.urlencode(),
        'price_bands': price_band_links(request),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('images'),
        slug=slug, is_active=True,
    )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'related_products': Product.objects.filter(
            category=product.category, is_active=True
        ).exclude(pk=product.pk)[:4],
    })
