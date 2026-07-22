from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from catalog.models import Category, Product

from .forms import ContactForm

CONTACT_EMAIL = getattr(settings, 'CONTACT_EMAIL', 'hello@example.com')


def home(request):
    return render(request, 'core/home.html', {
        'featured_products': Product.objects.filter(
            is_active=True
        ).select_related('category')[:8],
        # The banner takes the first three; the filter tabs need them all.
        'categories': Category.objects.all(),
        # "Deal of the week" is presentation only — the cheapest live product
        # stands in for it rather than inventing a promotions model.
        'deal_product': Product.objects.filter(
            is_active=True, stock__gt=0
        ).order_by('price').first(),
    })


def about(request):
    return render(request, 'core/about.html')


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            send_mail(
                subject=f"Contact form: {data['name']}",
                message=data['message'],
                from_email=None,
                recipient_list=[CONTACT_EMAIL],
                fail_silently=True,
            )
            messages.success(request, 'Thanks — we will get back to you shortly.')
            return redirect('core:contact')
        messages.error(request, 'Please check the form and try again.')
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {'form': form})
