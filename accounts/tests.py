from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Address, Profile

User = get_user_model()

ADDRESS = {
    'label': 'Home',
    'full_name': 'Wanjiku Kamau',
    'county': 'Nairobi',
    'town': 'Westlands',
    'street': '12 Rhapta Road',
}


class ProfileSignalTests(TestCase):
    def test_a_profile_is_created_with_the_user(self):
        user = User.objects.create_user('wanjiku', password='sekret123')
        self.assertIsInstance(user.profile, Profile)

    def test_saving_an_existing_user_does_not_add_a_second_profile(self):
        user = User.objects.create_user('wanjiku', password='sekret123')
        user.first_name = 'Wanjiku'
        user.save()
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)


class DefaultAddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('wanjiku', password='sekret123')

    def test_marking_one_default_demotes_the_others(self):
        first = Address.objects.create(user=self.user, is_default=True, **ADDRESS)
        second = Address.objects.create(
            user=self.user, is_default=True, **{**ADDRESS, 'label': 'Work'}
        )

        first.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)

    def test_another_users_default_is_left_alone(self):
        other = User.objects.create_user('other', password='sekret123')
        theirs = Address.objects.create(user=other, is_default=True, **ADDRESS)

        Address.objects.create(user=self.user, is_default=True, **ADDRESS)

        theirs.refresh_from_db()
        self.assertTrue(theirs.is_default)

    def test_default_address_sorts_first(self):
        Address.objects.create(user=self.user, **{**ADDRESS, 'label': 'Work'})
        default = Address.objects.create(
            user=self.user, is_default=True, **{**ADDRESS, 'label': 'Zanzibar'}
        )
        self.assertEqual(self.user.addresses.first(), default)


@override_settings(ALLOWED_HOSTS=['testserver'])
class AccountAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('wanjiku', password='sekret123')
        self.other = User.objects.create_user('other', password='sekret123')
        self.address = Address.objects.create(user=self.user, **ADDRESS)

    def test_profile_requires_signing_in(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)

    def test_profile_renders_for_its_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 200)

    def test_another_user_cannot_edit_your_address(self):
        self.client.force_login(self.other)
        response = self.client.get(
            reverse('accounts:address_edit', args=[self.address.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_another_user_cannot_delete_your_address(self):
        self.client.force_login(self.other)
        self.client.post(reverse('accounts:address_delete', args=[self.address.pk]))
        self.assertTrue(Address.objects.filter(pk=self.address.pk).exists())

    def test_owner_can_delete_their_address(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:address_delete', args=[self.address.pk]))
        self.assertFalse(Address.objects.filter(pk=self.address.pk).exists())
