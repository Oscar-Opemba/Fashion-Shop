from .models import Category, WishlistItem


def shop(request):
    """The nav's category dropdown, needed on every page."""
    return {'nav_categories': Category.objects.all()}


def wishlist(request):
    """Which products the signed-in shopper has saved, and how many.

    Every product card draws a filled or empty heart, and cards appear on the
    homepage, the listing, the related strip and the saved page. Without this,
    each of those four views would have to remember to pass the same set, and
    the card would run a query per product to find out.

    One `values_list` per request, and nothing at all for anonymous visitors —
    the card's `{% if user.is_authenticated %}` never reaches the set.
    """
    if not request.user.is_authenticated:
        return {'wishlist_ids': set(), 'wishlist_count': 0}

    ids = set(
        WishlistItem.objects.filter(user=request.user).values_list(
            'product_id', flat=True
        )
    )
    return {'wishlist_ids': ids, 'wishlist_count': len(ids)}
