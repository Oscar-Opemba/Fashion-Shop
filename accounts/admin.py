from django.contrib import admin

from .models import Address, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone']
    search_fields = ['user__email', 'user__username', 'phone']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'label', 'town', 'county', 'is_default']
    list_filter = ['is_default', 'county']
    search_fields = ['user__email', 'town', 'street']
