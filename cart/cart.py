from decimal import Decimal

from django.conf import settings

from catalog.models import Product


class Cart:
    """A shopping cart stored in the session.

    Keeping the cart in the session means anonymous shoppers can fill one
    without signing up first, and there is no table to clean up when they
    never come back.

    Prices are copied in at add time so a later price change does not
    silently rewrite what someone already put in their cart.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if cart is None:
            cart = self.session[settings.CART_SESSION_ID] = {}
        self.cart = cart

    def add(self, product, quantity=1, override_quantity=False):
        key = str(product.id)
        if key not in self.cart:
            self.cart[key] = {'quantity': 0, 'price': str(product.price)}

        if override_quantity:
            self.cart[key]['quantity'] = quantity
        else:
            self.cart[key]['quantity'] += quantity

        # Never let the cart hold more than exists, and drop it entirely if the
        # quantity lands at zero or below.
        self.cart[key]['quantity'] = min(self.cart[key]['quantity'], product.stock)
        if self.cart[key]['quantity'] <= 0:
            del self.cart[key]

        self.save()

    def remove(self, product):
        self.cart.pop(str(product.id), None)
        self.save()

    def save(self):
        self.session.modified = True

    def clear(self):
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(id__in=self.cart.keys())

        # Copy each entry, not just the outer dict. A shallow copy would share
        # the nested dicts with the session, so the Decimal conversion below
        # would be written back into it — and the session is serialised as
        # JSON, which cannot encode a Decimal.
        cart = {key: dict(item) for key, item in self.cart.items()}

        for product in products:
            cart[str(product.id)]['product'] = product

        for item in cart.values():
            # A product deleted since it was added leaves an entry with no
            # product attached; skip it rather than blowing up the page.
            if 'product' not in item:
                continue
            item['price'] = Decimal(item['price'])
            item['total_price'] = item['price'] * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())

    def get_total_price(self):
        return sum(
            (Decimal(item['price']) * item['quantity'] for item in self.cart.values()),
            Decimal('0'),
        )

    def has_stock_issues(self):
        """Products that went out of stock while sitting in the cart."""
        issues = []
        for item in self:
            if item['quantity'] > item['product'].stock:
                issues.append(item)
        return issues
