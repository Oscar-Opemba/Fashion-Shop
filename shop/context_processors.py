from .models import Category


def shop(request):
    """The nav's category dropdown, needed on every page."""
    return {'nav_categories': Category.objects.all()}
