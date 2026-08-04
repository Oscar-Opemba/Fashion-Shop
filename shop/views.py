from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import CategoryForm, ProductForm
from .models import Category, Colour, Product, Size

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


def facet_links(request, param, options):
    """Build sidebar links for a size/colour facet.

    Each link toggles its own value and drops `page`, so switching a facet
    never lands the shopper on a page number that no longer exists. Other
    active filters are carried through untouched.
    """
    active = request.GET.get(param, '').strip()
    links = []
    for option in options:
        params = request.GET.copy()
        params.pop('page', None)
        is_active = option.slug == active
        if is_active:
            params.pop(param, None)
        else:
            params[param] = option.slug
        links.append({
            'option': option,
            'active': is_active,
            'query': params.urlencode(),
        })
    return links


def money(value):
    """`2000` or the string `'2000'` -> `'2,000'`.

    The bands above pass ints; the chip builder passes whatever was in the
    url, which may be junk. Junk is shown back verbatim rather than raising —
    it is already being ignored by the filtering itself.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f'{number:,.0f}' if number == int(number) else f'{number:,.2f}'


def price_band_label(low, high):
    if low is None:
        return f'Under KES {money(high)}'
    if high is None:
        return f'KES {money(low)}+'
    return f'KES {money(low)} - {money(high)}'


def price_band_links(request):
    """Build the sidebar's price links, keeping any other active filters."""
    current = (
        request.GET.get('min_price', '').strip(),
        request.GET.get('max_price', '').strip(),
    )
    links = []
    for low, high in PRICE_BANDS:
        params = request.GET.copy()
        for key in ('page', 'min_price', 'max_price'):
            params.pop(key, None)

        # A band is showing if the url carries exactly its bounds. Comparing
        # as strings keeps `?min_price=2000` and `?min_price=2000.0` from
        # looking like different bands to the shopper.
        is_active = current == (
            str(low) if low is not None else '',
            str(high) if high is not None else '',
        )

        # Clicking the band you are already on clears it, the same way the
        # size and colour facets behave.
        if not is_active:
            if low is not None:
                params['min_price'] = low
            if high is not None:
                params['max_price'] = high

        links.append({
            'label': price_band_label(low, high),
            'query': params.urlencode(),
            'active': is_active,
        })
    return links


def drop_params(request, *keys):
    """The current querystring without `keys` (or `page`).

    Used by the chips above the grid, each of which removes one filter and
    leaves the others alone.
    """
    params = request.GET.copy()
    for key in keys + ('page',):
        params.pop(key, None)
    return params.urlencode()


def active_filter_chips(request, active_category, active_size, active_colour, query):
    """Describe every filter currently narrowing the grid.

    The sidebar could be carrying four filters at once with nothing above the
    results saying so, and no way to lift one without hunting for the link
    that set it. Each chip names a filter and links to the listing without it.
    """
    chips = []

    if query:
        chips.append({
            'label': f'Search: {query}',
            'query': drop_params(request, 'q'),
        })

    if active_category:
        chips.append({
            'label': active_category.name,
            'query': drop_params(request, 'category'),
        })

    if active_size:
        chips.append({
            'label': f'Size {active_size.name}',
            'query': drop_params(request, 'size'),
        })

    if active_colour:
        chips.append({
            'label': active_colour.name,
            'swatch': active_colour.hex_value,
            'query': drop_params(request, 'colour'),
        })

    # Price is two parameters but reads as one filter, so it gets one chip
    # that clears both. An unrecognised pair still gets a chip — a
    # hand-edited url must be as easy to escape as one we rendered.
    low = request.GET.get('min_price', '').strip()
    high = request.GET.get('max_price', '').strip()
    if low or high:
        chips.append({
            'label': price_band_label(low or None, high or None),
            'query': drop_params(request, 'min_price', 'max_price'),
        })

    return chips


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

    size_slug = request.GET.get('size', '').strip()
    active_size = None
    if size_slug:
        active_size = Size.objects.filter(slug=size_slug).first()
        # An unknown slug filters nothing rather than 404ing — these come from
        # bookmarked or hand-edited urls, not from a link we rendered.
        products = products.filter(sizes=active_size) if active_size else products.none()

    colour_slug = request.GET.get('colour', '').strip()
    active_colour = None
    if colour_slug:
        active_colour = Colour.objects.filter(slug=colour_slug).first()
        products = (
            products.filter(colours=active_colour) if active_colour else products.none()
        )

    sort = request.GET.get('sort', '')
    products = products.order_by(
        {'price': 'price', '-price': '-price', 'name': 'name'}.get(sort, '-created')
    )

    page = Paginator(products, PAGE_SIZE).get_page(request.GET.get('page'))

    # Preserve the active filters when building pagination links.
    params = request.GET.copy()
    params.pop('page', None)

    return render(request, 'shop/product_list.html', {
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
        # Only offer facet values that some live product actually carries,
        # otherwise the sidebar advertises filters that return nothing.
        'size_links': facet_links(
            request, 'size', Size.objects.filter(products__is_active=True).distinct()
        ),
        'colour_links': facet_links(
            request, 'colour', Colour.objects.filter(products__is_active=True).distinct()
        ),
        'active_size': active_size,
        'active_colour': active_colour,
        'active_filters': active_filter_chips(
            request, active_category, active_size, active_colour, query
        ),
        # "Clear all" drops every filter but keeps the sort, which is a
        # display preference rather than one of them.
        'clear_query': drop_params(
            request, 'q', 'category', 'size', 'colour', 'min_price', 'max_price'
        ),
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related(
            'images', 'sizes', 'colours'
        ),
        slug=slug, is_active=True,
    )

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'related_products': Product.objects.filter(
            category=product.category, is_active=True
        ).exclude(pk=product.pk)[:4],
    })


# ---------------------------------------------------------------------------
# Staff catalogue management — the CRUD half.
#
# `product_list` and `product_detail` above are the public Read side and stay
# function-based: their filtering does not fit a ListView's get_queryset
# without spreading across three hooks. Everything below is a class-based
# view, since Create/Update/Delete are exactly the shapes Django ships.
#
# This is a convenience surface, not a replacement for /admin/ — it is gated
# to staff and reuses the same model forms.
# ---------------------------------------------------------------------------


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Signed in *and* staff. Anonymous users are sent to log in; a signed-in
    shopper who guesses a manage url gets a 403 rather than a login loop."""

    def test_func(self):
        return self.request.user.is_staff


class ProtectedDeleteMixin:
    """Turn a PROTECT violation into a message instead of a 500.

    `OrderItem.product` and `Product.category` are PROTECT, so anything that
    has been sold — or any category still holding products — cannot be
    deleted. That is the intended answer, not an error page.
    """

    protected_message = 'Cannot delete this — other records still reference it.'
    success_message = 'Deleted.'

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, self.protected_message)
            return redirect(self.get_success_url())
        messages.success(self.request, self.success_message)
        return response


class ProductManageList(StaffRequiredMixin, ListView):
    """Read, staff flavour — includes the inactive rows the shop hides."""

    model = Product
    template_name = 'shop/manage_list.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        products = Product.objects.select_related('category')
        query = self.request.GET.get('q', '').strip()
        if query:
            products = products.filter(name__icontains=query)
        return products

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()
        context['categories'] = Category.objects.annotate(
            product_count=Count('products')
        )
        return context


class ProductCreateView(StaffRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('shop:manage_list')
    extra_context = {'title': 'Add product'}

    def form_valid(self, form):
        messages.success(self.request, 'Product created.')
        return super().form_valid(form)


class ProductUpdateView(StaffRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('shop:manage_list')
    extra_context = {'title': 'Edit product'}

    def form_valid(self, form):
        messages.success(self.request, 'Product updated.')
        return super().form_valid(form)


class ProductDeleteView(ProtectedDeleteMixin, StaffRequiredMixin, DeleteView):
    model = Product
    template_name = 'shop/product_confirm_delete.html'
    success_url = reverse_lazy('shop:manage_list')
    success_message = 'Product deleted.'
    protected_message = (
        'That product appears in an order, so it cannot be deleted. '
        'Untick "is active" to retire it instead.'
    )


class CategoryCreateView(StaffRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('shop:manage_list')
    extra_context = {'title': 'Add category'}

    def form_valid(self, form):
        messages.success(self.request, 'Category created.')
        return super().form_valid(form)


class CategoryUpdateView(StaffRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'shop/product_form.html'
    success_url = reverse_lazy('shop:manage_list')
    extra_context = {'title': 'Edit category'}

    def form_valid(self, form):
        messages.success(self.request, 'Category updated.')
        return super().form_valid(form)


class CategoryDeleteView(ProtectedDeleteMixin, StaffRequiredMixin, DeleteView):
    model = Category
    template_name = 'shop/category_confirm_delete.html'
    success_url = reverse_lazy('shop:manage_list')
    success_message = 'Category deleted.'
    protected_message = (
        'That category still holds products, so it cannot be deleted. '
        'Move them to another category first.'
    )
