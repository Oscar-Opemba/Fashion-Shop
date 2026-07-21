from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ReviewForm
from .models import Category, Product, WishlistItem

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
    products = (
        Product.objects.filter(is_active=True)
        .select_related('category')
        .annotate(avg_rating=Avg('reviews__rating'))
    )

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

    reviews = product.reviews.select_related('user')
    stats = reviews.aggregate(average=Avg('rating'), total=Count('id'))

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'average_rating': stats['average'],
        'review_count': stats['total'],
        'review_form': ReviewForm(),
        'already_reviewed': (
            request.user.is_authenticated
            and reviews.filter(user=request.user).exists()
        ),
        'related_products': Product.objects.filter(
            category=product.category, is_active=True
        ).exclude(pk=product.pk)[:4],
        'in_wishlist': (
            request.user.is_authenticated
            and WishlistItem.objects.filter(
                user=request.user, product=product
            ).exists()
        ),
    })


@login_required
@require_POST
def review_add(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    if product.reviews.filter(user=request.user).exists():
        messages.info(request, 'You have already reviewed this product.')
        return redirect(product)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.save()
        messages.success(request, 'Thanks for your review.')
    else:
        messages.error(request, 'Please pick a rating and write a comment.')

    return redirect(product)


@login_required
@require_POST
def wishlist_toggle(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)

    item, created = WishlistItem.objects.get_or_create(
        user=request.user, product=product
    )
    if not created:
        item.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'in_wishlist': created,
            'count': WishlistItem.objects.filter(user=request.user).count(),
        })

    messages.success(
        request,
        'Added to your wishlist.' if created else 'Removed from your wishlist.',
    )
    return redirect(product)


@login_required
def wishlist(request):
    items = (
        WishlistItem.objects
        .filter(user=request.user)
        .select_related('product', 'product__category')
    )
    return render(request, 'catalog/wishlist.html', {'items': items})
