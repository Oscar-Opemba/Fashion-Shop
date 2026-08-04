"""Prove the mail configuration works, and say precisely what is wrong if not.

    python manage.py mailcheck                 # report the config, connect, log in
    python manage.py mailcheck --to a@b.com    # ...and actually send a test message
    python manage.py mailcheck --receipt 15    # ...re-send order 15's real receipt

Django ships `sendtestemail`, which sends and reports whatever exception comes
back. That is not much help here: the two failures this setup actually hits are
a blocked outbound port and a Google account without an App Password, and both
of those arrive as a wall of SMTP jargon. This separates the steps — settings,
then TCP, then TLS, then AUTH, then send — so the first one that fails names
itself.
"""

import smtplib
import socket

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.core.management.base import BaseCommand, CommandError

from orders.models import Order
from orders.notifications import send_receipt


class Command(BaseCommand):
    help = 'Check the email settings, then optionally send a test message.'

    def add_arguments(self, parser):
        parser.add_argument('--to', help='Send a test message to this address.')
        parser.add_argument(
            '--receipt', type=int, metavar='ORDER_ID',
            help="Re-send a real order's receipt to the address on the order.",
        )

    def handle(self, *args, **options):
        ok = self.style.SUCCESS
        bad = self.style.ERROR
        warn = self.style.WARNING

        backend = settings.EMAIL_BACKEND
        user = settings.EMAIL_HOST_USER
        password = settings.EMAIL_HOST_PASSWORD

        self.stdout.write('Configuration')
        self.stdout.write(f'  backend    {backend}')
        self.stdout.write(f'  host       {settings.EMAIL_HOST}:{settings.EMAIL_PORT}')
        self.stdout.write(f'  TLS / SSL  {settings.EMAIL_USE_TLS} / {settings.EMAIL_USE_SSL}')
        self.stdout.write(f'  user       {user or "(unset)"}')
        # Never the value. Its length is enough to catch the usual mistake,
        # which is pasting something that is not a 16-character App Password.
        self.stdout.write(
            f'  password   {"set, " + str(len(password)) + " chars" if password else "(unset)"}'
        )
        self.stdout.write(f'  from       {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'  timeout    {settings.EMAIL_TIMEOUT}s')
        self.stdout.write('')

        if 'console' in backend:
            self.stdout.write(warn(
                'Console backend: nothing will be sent, messages print to this '
                'terminal.\nSet EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env '
                'to switch to real mail.'
            ))
            if not (options['to'] or options['receipt']):
                return

        if 'smtp' in backend:
            self._check_smtp(user, password, ok, bad)

        if options['to']:
            self._send_test(options['to'], ok, bad)

        if options['receipt']:
            self._resend_receipt(options['receipt'], ok, bad)

    def _check_smtp(self, user, password, ok, bad):
        host, port = settings.EMAIL_HOST, settings.EMAIL_PORT

        self.stdout.write(f'Reaching {host}:{port} ...')
        try:
            socket.create_connection((host, port), timeout=settings.EMAIL_TIMEOUT).close()
        except OSError as exc:
            raise CommandError(
                f'Cannot open a socket to {host}:{port} ({type(exc).__name__}).\n'
                "On PythonAnywhere's free tier most SMTP hosts are refused — "
                'Gmail is reachable, SendGrid and Brevo are not. If you are on '
                'that tier, use smtp.gmail.com.'
            )
        self.stdout.write(ok('  socket open'))

        self.stdout.write('Negotiating TLS and logging in ...')
        try:
            server = smtplib.SMTP(host, port, timeout=settings.EMAIL_TIMEOUT)
            server.ehlo()
            if settings.EMAIL_USE_TLS:
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.quit()
        except smtplib.SMTPAuthenticationError as exc:
            raise CommandError(
                f'The server refused those credentials ({exc.smtp_code}).\n'
                'For Gmail this is almost always one of:\n'
                '  - EMAIL_HOST_PASSWORD is the account password rather than an '
                'App Password\n'
                '  - 2-Step Verification is off, so App Passwords cannot exist\n'
                '  - the App Password was revoked\n'
                'Create one at https://myaccount.google.com/apppasswords'
            )
        except (smtplib.SMTPException, OSError) as exc:
            raise CommandError(f'{type(exc).__name__}: {exc}')
        self.stdout.write(ok('  authenticated'))

    def _send_test(self, to, ok, bad):
        self.stdout.write(f'Sending a test message to {to} ...')
        sent = send_mail(
            subject=f'{getattr(settings, "SITE_NAME", "Fashion Shop")} — mail check',
            message=(
                'If you are reading this, the shop can send email.\n\n'
                'Order receipts will now reach shoppers who leave an address at '
                'checkout.'
            ),
            from_email=None,
            recipient_list=[to],
            fail_silently=False,
            connection=get_connection(),
        )
        self.stdout.write(ok(f'  sent ({sent} message)') if sent else bad('  nothing sent'))

    def _resend_receipt(self, order_id, ok, bad):
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            raise CommandError(f'No order #{order_id}.')

        if not order.email:
            raise CommandError(
                f'Order #{order_id} has no email address — checkout leaves that '
                'field optional, so guests who skip it get no receipt.'
            )

        self.stdout.write(f'Re-sending the receipt for #{order_id} to {order.email} ...')
        self.stdout.write(
            ok('  sent') if send_receipt(order)
            else bad('  failed — see the traceback in the log')
        )
