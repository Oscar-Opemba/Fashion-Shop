from .models import Category


def catalog(request):
    """The nav's category dropdown, needed on every page."""
    return {'nav_categories': Category.objects.all()}
