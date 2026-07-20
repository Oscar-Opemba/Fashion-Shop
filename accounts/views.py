from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AddressForm, ProfileForm
from .models import Address


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(
            request.POST, request.FILES, instance=request.user.profile
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user.profile)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'addresses': request.user.addresses.all(),
    })


@login_required
def address_create(request):
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # The first address a user saves is their default.
            if not request.user.addresses.exists():
                address.is_default = True
            address.save()
            messages.success(request, 'Address saved.')
            return redirect('accounts:profile')
    else:
        form = AddressForm(initial={'full_name': request.user.get_full_name()})

    return render(request, 'accounts/address_form.html', {
        'form': form, 'title': 'Add address',
    })


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated.')
            return redirect('accounts:profile')
    else:
        form = AddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {
        'form': form, 'title': 'Edit address', 'address': address,
    })


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address removed.')
        return redirect('accounts:profile')
    return render(request, 'accounts/address_confirm_delete.html', {
        'address': address,
    })
