from django.contrib.auth import get_user_model
from django.core import mail
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


@override_settings(ALLOWED_HOSTS=['testserver'])
class AuthFlowTests(TestCase):
    """Sign up, sign in, sign out — the allauth routes, exercised for real.

    The rest of this file trusts `force_login()`. These do not: they post the
    forms a shopper actually posts, which is the only way a broken template or
    a changed allauth setting shows up.
    """

    EMAIL = 'wanjiku@example.com'
    PASSWORD = 'sekret-passphrase-123'

    def signed_in(self, response):
        return response.wsgi_request.user.is_authenticated

    def test_signup_creates_a_user_and_signs_them_in(self):
        response = self.client.post(reverse('account_signup'), {
            'email': self.EMAIL,
            'password1': self.PASSWORD,
            'password2': self.PASSWORD,
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email=self.EMAIL)
        self.assertTrue(self.signed_in(response))
        # The post_save signal has to have run for the profile page to work.
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_signup_rejects_mismatched_passwords(self):
        self.client.post(reverse('account_signup'), {
            'email': self.EMAIL,
            'password1': self.PASSWORD,
            'password2': 'something-else-entirely',
        })
        self.assertFalse(User.objects.filter(email=self.EMAIL).exists())

    def test_login_is_by_email_not_username(self):
        """ACCOUNT_LOGIN_METHODS = {'email'} — the form has no username field."""
        User.objects.create_user('wanjiku', self.EMAIL, self.PASSWORD)

        response = self.client.post(reverse('account_login'), {
            'login': self.EMAIL, 'password': self.PASSWORD,
        }, follow=True)
        self.assertTrue(self.signed_in(response))

    def test_login_with_the_wrong_password_fails(self):
        User.objects.create_user('wanjiku', self.EMAIL, self.PASSWORD)

        response = self.client.post(reverse('account_login'), {
            'login': self.EMAIL, 'password': 'not-the-password',
        }, follow=True)
        self.assertFalse(self.signed_in(response))

    def test_logout_needs_a_post(self):
        """A GET must not sign anyone out — any <img> tag on another site
        could trigger one."""
        user = User.objects.create_user('wanjiku', self.EMAIL, self.PASSWORD)
        self.client.force_login(user)

        self.client.get(reverse('account_logout'))
        self.assertTrue(self.signed_in(self.client.get(reverse('core:home'))))

        self.client.post(reverse('account_logout'))
        self.assertFalse(self.signed_in(self.client.get(reverse('core:home'))))


@override_settings(ALLOWED_HOSTS=['testserver'])
class PasswordResetTests(TestCase):
    """The four-step reset flow, end to end, through our own templates."""

    EMAIL = 'wanjiku@example.com'
    OLD_PASSWORD = 'sekret-passphrase-123'
    NEW_PASSWORD = 'a-completely-different-one-456'

    def setUp(self):
        self.user = User.objects.create_user(
            'wanjiku', self.EMAIL, self.OLD_PASSWORD
        )

    def request_reset(self, email=None):
        return self.client.post(
            reverse('account_reset_password'),
            {'email': email or self.EMAIL},
            follow=True,
        )

    def reset_link(self, message):
        """Pull the reset path out of the emailed body."""
        for word in message.body.split():
            if '/accounts/password/reset/key/' in word:
                return word[word.index('/accounts/'):]
        self.fail(f'no reset link in:\n{message.body}')

    def test_our_templates_are_used_not_allauths(self):
        response = self.client.get(reverse('account_reset_password'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/password_reset.html')
        self.assertContains(response, 'Send reset link')

    def test_requesting_a_reset_sends_a_link(self):
        response = self.request_reset()
        self.assertTemplateUsed(response, 'account/password_reset_done.html')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.EMAIL, mail.outbox[0].to)

    def test_an_unknown_address_looks_identical(self):
        """No account enumeration: the page must not reveal who has an account."""
        known = self.request_reset()
        mail.outbox.clear()
        unknown = self.request_reset('nobody@example.com')

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.content, unknown.content)

    def test_the_link_sets_a_new_password(self):
        self.request_reset()
        # GET the emailed url first: allauth moves the key into the session
        # and redirects, so the key never sits in the address bar afterwards.
        landing = self.client.get(self.reset_link(mail.outbox[0]), follow=True)
        self.assertTemplateUsed(landing, 'account/password_reset_from_key.html')

        done = self.client.post(landing.request['PATH_INFO'], {
            'password1': self.NEW_PASSWORD,
            'password2': self.NEW_PASSWORD,
        }, follow=True)
        self.assertTemplateUsed(
            done, 'account/password_reset_from_key_done.html'
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.NEW_PASSWORD))
        self.assertFalse(self.user.check_password(self.OLD_PASSWORD))

    def test_the_link_cannot_be_used_twice(self):
        self.request_reset()
        link = self.reset_link(mail.outbox[0])

        landing = self.client.get(link, follow=True)
        self.client.post(landing.request['PATH_INFO'], {
            'password1': self.NEW_PASSWORD,
            'password2': self.NEW_PASSWORD,
        }, follow=True)

        # Second time around the key is spent, and the template says so
        # rather than 404ing.
        replay = self.client.get(link, follow=True)
        self.assertContains(replay, 'no longer works')

    def test_the_new_password_signs_in_and_the_old_one_does_not(self):
        self.request_reset()
        landing = self.client.get(self.reset_link(mail.outbox[0]), follow=True)
        self.client.post(landing.request['PATH_INFO'], {
            'password1': self.NEW_PASSWORD,
            'password2': self.NEW_PASSWORD,
        }, follow=True)

        stale = self.client.post(reverse('account_login'), {
            'login': self.EMAIL, 'password': self.OLD_PASSWORD,
        }, follow=True)
        self.assertFalse(stale.wsgi_request.user.is_authenticated)

        fresh = self.client.post(reverse('account_login'), {
            'login': self.EMAIL, 'password': self.NEW_PASSWORD,
        }, follow=True)
        self.assertTrue(fresh.wsgi_request.user.is_authenticated)
