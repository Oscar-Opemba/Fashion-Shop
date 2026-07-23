from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from shop.models import Product

from .cart import Cart


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _cart_payload(request, cart):
    return {
        'count': len(cart),
        'total': f'{cart.get_total_price():.2f}',
        'summary_html': render_to_string(
            'cart/_summary.html', {'cart': cart}, request=request
        ),
    }


def cart_detail(request):
    return render(request, 'cart/detail.html', {'cart': Cart(request)})


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id, is_active=True)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except ValueError:
        quantity = 1

    override = request.POST.get('override') == 'true'

    if not product.in_stock:
        if _is_ajax(request):
            return JsonResponse(
                {'error': f'{product.name} is out of stock.'}, status=400
            )
        messages.error(request, f'{product.name} is out of stock.')
        return redirect(product)

    cart.add(product, quantity=quantity, override_quantity=override)

    if _is_ajax(request):
        return JsonResponse(_cart_payload(request, cart))

    messages.success(request, f'{product.name} added to your cart.')
    return redirect('cart:detail')


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)

    if _is_ajax(request):
        return JsonResponse(_cart_payload(request, cart))

    messages.success(request, f'{product.name} removed from your cart.')
    return redirect('cart:detail')


@require_POST
def cart_clear(request):
    Cart(request).clear()
    messages.success(request, 'Your cart is empty.')
    return redirect('cart:detail')
