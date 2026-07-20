from .cart import Cart


def cart(request):
    """The header shows an item count and running total on every page."""
    return {'cart': Cart(request)}
