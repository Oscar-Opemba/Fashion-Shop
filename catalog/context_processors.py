from .models import Category, WishlistItem


def catalog(request):
    """Nav categories and the wishlist badge, needed on every page."""
    wishlist_count = 0
    if request.user.is_authenticated:
        wishlist_count = WishlistItem.objects.filter(user=request.user).count()

    return {
        'nav_categories': Category.objects.all(),
        'wishlist_count': wishlist_count,
    }
