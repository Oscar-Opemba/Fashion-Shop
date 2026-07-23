"""Thin client for Safaricom's Daraja API (Lipa na M-Pesa Online / STK Push).

Deliberately no SDK: the surface we need is three HTTP calls, and keeping it
explicit makes the request/response shapes visible when debugging.
"""

import base64
import logging
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

BASE_URLS = {
    'sandbox': 'https://sandbox.safaricom.co.ke',
    'production': 'https://api.safaricom.co.ke',
}

TOKEN_CACHE_KEY = 'mpesa:access_token'
# Daraja tokens last ~3599s. Expiring ours early avoids racing the boundary.
TOKEN_CACHE_SECONDS = 3300

REQUEST_TIMEOUT = 30


class DarajaError(Exception):
    """Raised when Daraja rejects a request or is unreachable."""


def base_url():
    return BASE_URLS.get(settings.MPESA_ENV, BASE_URLS['sandbox'])


def normalise_phone(raw):
    """Convert the ways Kenyans actually type a number into 2547XXXXXXXX.

    Accepts 0712345678, +254712345678, 254712345678, 712345678 and the
    Airtel/Safaricom 011x range. Returns None if it is not a valid MSISDN.
    """
    if not raw:
        return None

    digits = re.sub(r'\D', '', str(raw))

    if digits.startswith('254'):
        national = digits[3:]
    elif digits.startswith('0'):
        national = digits[1:]
    elif len(digits) == 9:
        national = digits
    else:
        return None

    # Kenyan mobile numbers are 9 digits nationally and start with 7 or 1.
    if len(national) != 9 or national[0] not in '71':
        return None

    return f'254{national}'


def get_access_token(force_refresh=False):
    if not force_refresh:
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return cached

    if not settings.MPESA_CONSUMER_KEY or not settings.MPESA_CONSUMER_SECRET:
        raise DarajaError(
            'MPESA_CONSUMER_KEY / MPESA_CONSUMER_SECRET are not set. '
            'Add them to your .env file.'
        )

    try:
        response = requests.get(
            f'{base_url()}/oauth/v1/generate',
            params={'grant_type': 'client_credentials'},
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise DarajaError(f'Could not reach Daraja: {exc}') from exc

    if response.status_code != 200:
        raise DarajaError(
            f'Daraja auth failed ({response.status_code}): {response.text}'
        )

    token = response.json().get('access_token')
    if not token:
        raise DarajaError(f'Daraja auth returned no token: {response.text}')

    cache.set(TOKEN_CACHE_KEY, token, TOKEN_CACHE_SECONDS)
    return token


def _password(timestamp):
    raw = f'{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}'
    return base64.b64encode(raw.encode()).decode()


def callback_url():
    base = (settings.MPESA_CALLBACK_BASE_URL or '').rstrip('/')
    if not base:
        raise DarajaError(
            'MPESA_CALLBACK_BASE_URL is not set. Safaricom needs a public '
            'https url to post the result to — run `ngrok http 8000` and put '
            'the forwarding url in your .env file.'
        )
    return f'{base}/payments/callback/{settings.MPESA_CALLBACK_TOKEN}/'


def stk_push(phone, amount, account_reference, description=None):
    """Send an STK push. Returns Daraja's parsed JSON response.

    `amount` must be a whole number of shillings — Daraja rejects decimals.
    """
    msisdn = normalise_phone(phone)
    if msisdn is None:
        raise DarajaError(f'Not a valid phone number: {phone!r}')

    if not settings.MPESA_PASSKEY:
        raise DarajaError('MPESA_PASSKEY is not set. Add it to your .env file.')

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

    payload = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password': _password(timestamp),
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(amount),
        'PartyA': msisdn,
        'PartyB': settings.MPESA_SHORTCODE,
        'PhoneNumber': msisdn,
        'CallBackURL': callback_url(),
        # Daraja caps these two fields; over-long values are rejected outright.
        'AccountReference': str(account_reference)[:12],
        'TransactionDesc': (description or settings.MPESA_TRANSACTION_DESC)[:13],
    }

    token = get_access_token()

    try:
        response = requests.post(
            f'{base_url()}/mpesa/stkpush/v1/processrequest',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise DarajaError(f'Could not reach Daraja: {exc}') from exc

    # An expired-but-cached token shows up as a 401; refresh once and retry.
    if response.status_code == 401:
        token = get_access_token(force_refresh=True)
        try:
            response = requests.post(
                f'{base_url()}/mpesa/stkpush/v1/processrequest',
                json=payload,
                headers={'Authorization': f'Bearer {token}'},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise DarajaError(f'Could not reach Daraja: {exc}') from exc

    try:
        data = response.json()
    except ValueError:
        raise DarajaError(
            f'Daraja returned non-JSON ({response.status_code}): {response.text}'
        )

    if response.status_code != 200 or str(data.get('ResponseCode')) != '0':
        message = (
            data.get('errorMessage')
            or data.get('ResponseDescription')
            or response.text
        )
        raise DarajaError(f'STK push rejected: {message}')

    return data


def query_stk_status(checkout_request_id):
    """Ask Daraja what happened to a push, for when the callback never lands.

    Returns None on any failure. This is a best-effort helper polled from a
    page the shopper is watching, so it must never raise — an unconfigured or
    unreachable Daraja should leave the checkout waiting, not error out.
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        payload = {
            'BusinessShortCode': settings.MPESA_SHORTCODE,
            'Password': _password(timestamp),
            'Timestamp': timestamp,
            'CheckoutRequestID': checkout_request_id,
        }
        response = requests.post(
            f'{base_url()}/mpesa/stkpushquery/v1/query',
            json=payload,
            headers={'Authorization': f'Bearer {get_access_token()}'},
            timeout=REQUEST_TIMEOUT,
        )
        return response.json()
    except (DarajaError, requests.RequestException, ValueError) as exc:
        logger.warning('STK status query failed for %s: %s', checkout_request_id, exc)
        return None
