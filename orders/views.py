from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from cart.cart import Cart
from shop.models import Product

from .forms import CouponApplyForm, OrderCreateForm
from .models import Order, OrderItem

COUPON_SESSION_ID = 'coupon_id'


def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.info(request, 'Your cart is empty.')
        return redirect('shop:product_list')

    issues = cart.has_stock_issues()
    if issues:
        for item in issues:
            messages.error(
                request,
                f"Only {item['product'].stock} left of {item['product'].name}. "
                'Please update your cart.',
            )
        return redirect('cart:detail')

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                if request.user.is_authenticated:
                    order.user = request.user

                coupon = _session_coupon(request)
                if coupon:
                    order.coupon = coupon
                    order.discount_percent = coupon.discount_percent

                order.save()

                # Prices come from the cart, not the product, so what the
                # shopper agreed to is what gets charged.
                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        product=item['product'],
                        price=item['price'],
                        quantity=item['quantity'],
                    )
                    for item in cart
                ])

                # The order is the commitment, so the stock goes with it.
                for item in cart:
                    product = Product.objects.select_for_update().get(
                        pk=item['product'].pk
                    )
                    product.stock = max(0, product.stock - item['quantity'])
                    product.save(update_fields=['stock'])

            if not order.user_id:
                # A guest's claim on an order is recorded here, at the only
                # moment we know it is genuinely theirs. Recording it later
                # would let anyone claim an order by walking ids and then read
                # the buyer's name, phone and address.
                owned = request.session.get('guest_orders', [])
                owned.append(order.pk)
                request.session['guest_orders'] = owned[-20:]

            cart.clear()
            request.session.pop(COUPON_SESSION_ID, None)

            return redirect('orders:placed', order_id=order.pk)
    else:
        form = OrderCreateForm(initial=_prefill(request))

    coupon = _session_coupon(request)
    subtotal = cart.get_total_price()
    discount = (
        (subtotal * coupon.discount_percent / Decimal('100')).quantize(Decimal('0.01'))
        if coupon else Decimal('0')
    )

    return render(request, 'orders/checkout.html', {
        'cart': cart,
        'form': form,
        'coupon_form': CouponApplyForm(),
        'coupon': coupon,
        'subtotal': subtotal,
        'discount': discount,
        'total': subtotal - discount,
    })


def order_placed(request, order_id):
    """Confirmation page, reachable by the guest who placed the order too."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'), pk=order_id
    )

    if not _owns_order(request, order):
        raise Http404

    return render(request, 'orders/placed.html', {'order': order})


def _owns_order(request, order):
    """A member's order is tied to the user, a guest's to their session.

    Guest claims are written by the checkout view when the order is created,
    never here — otherwise walking order ids would hand out other people's
    delivery details.
    """
    if order.user_id:
        return request.user.is_authenticated and order.user_id == request.user.id
    return order.pk in request.session.get('guest_orders', [])


def _prefill(request):
    """Pre-populate checkout from the signed-in user's default address."""
    if not request.user.is_authenticated:
        return {}

    initial = {'email': request.user.email}

    profile = getattr(request.user, 'profile', None)
    if profile and profile.phone:
        initial['phone'] = profile.phone

    address = request.user.addresses.filter(is_default=True).first()
    if address:
        initial.update({
            'full_name': address.full_name,
            'county': address.county,
            'town': address.town,
            'street': address.street,
        })
    elif request.user.get_full_name():
        initial['full_name'] = request.user.get_full_name()

    return initial


def _session_coupon(request):
    from .models import Coupon

    coupon_id = request.session.get(COUPON_SESSION_ID)
    if not coupon_id:
        return None

    coupon = Coupon.objects.filter(id=coupon_id).first()
    if coupon and coupon.is_valid:
        return coupon

    request.session.pop(COUPON_SESSION_ID, None)
    return None


def coupon_apply(request):
    if request.method == 'POST':
        form = CouponApplyForm(request.POST)
        if form.is_valid():
            request.session[COUPON_SESSION_ID] = form.coupon.id
            messages.success(
                request, f'Coupon applied: {form.coupon.discount_percent}% off.'
            )
        else:
            messages.error(request, 'That coupon is not valid.')
    return redirect('orders:checkout')


def coupon_remove(request):
    request.session.pop(COUPON_SESSION_ID, None)
    messages.info(request, 'Coupon removed.')
    return redirect('orders:checkout')


@login_required
def order_history(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('items__product')
    )
    return render(request, 'orders/history.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        pk=order_id, user=request.user,
    )
    return render(request, 'orders/detail.html', {'order': order})
