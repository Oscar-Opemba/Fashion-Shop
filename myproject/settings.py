"""
Django settings for myproject.

Secrets and environment-specific values are read from a .env file at the
project root (see .env.example). Never commit .env.
"""

from pathlib import Path

from django.contrib.messages import constants as message_constants
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [v.strip() for v in env(name, default).split(',') if v.strip()]


SECRET_KEY = env('SECRET_KEY', 'django-insecure-dev-only-change-me')

DEBUG = env_bool('DEBUG', True)

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# A tunnel or proxy serving the site over https on a foreign host has to be
# trusted explicitly or every POST fails CSRF checks.
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'crispy_forms',
    'crispy_bootstrap4',
    'django_ckeditor_5',
    'embed_video',

    # Local
    'core',
    'shop',
    'cart',
    'orders',
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'myproject.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'shop.context_processors.shop',
            ],
        },
    },
]

WSGI_APPLICATION = 'myproject.wsgi.application'


# Database

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Nairobi'

USE_I18N = True

USE_TZ = True


# Static files and user uploads

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Authentication (django-allauth)

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_UNIQUE_EMAIL = True

LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = 'core:home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'core:home'

# Console backend keeps password-reset mails visible during development.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Social login (Google, Facebook)
# Credentials are read from the environment rather than the admin's SocialApp
# table, so a fresh clone needs no database fixture. A provider whose keys are
# absent is not registered at all, and the sign-in page then omits its button —
# that is what makes this safe to ship with the keys unset.

SOCIALACCOUNT_PROVIDERS = {}

if env('GOOGLE_CLIENT_ID') and env('GOOGLE_CLIENT_SECRET'):
    SOCIALACCOUNT_PROVIDERS['google'] = {
        'APP': {
            'client_id': env('GOOGLE_CLIENT_ID'),
            'secret': env('GOOGLE_CLIENT_SECRET'),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        # No refresh token: the shop only needs the identity at sign-in time.
        'AUTH_PARAMS': {'access_type': 'online'},
    }

if env('FACEBOOK_CLIENT_ID') and env('FACEBOOK_CLIENT_SECRET'):
    SOCIALACCOUNT_PROVIDERS['facebook'] = {
        'APP': {
            'client_id': env('FACEBOOK_CLIENT_ID'),
            'secret': env('FACEBOOK_CLIENT_SECRET'),
            'key': '',
        },
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'first_name', 'last_name', 'name', 'email'],
    }

# The provider supplies the email, so there is nothing left to ask for and the
# intermediate signup form is skipped.
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'

# Someone who registered with a password and later clicks "Continue with
# Google" should land in their existing account, not hit "an account already
# exists with this email". allauth only links the two when the provider says
# the address is verified — true for Google, not for Facebook, which is why
# Facebook still routes such a collision through the normal error path.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# Access/refresh tokens are never used after login, so they are not persisted.
SOCIALACCOUNT_STORE_TOKENS = False


# Messages
# includes/messages.html renders `alert-{{ message.tags }}`, so the tags have
# to be Bootstrap contextual names. Only ERROR differs — Django calls it
# 'error', Bootstrap calls it 'danger'.

MESSAGE_TAGS = {
    message_constants.DEBUG: 'secondary',
    message_constants.ERROR: 'danger',
}


# Production hardening
# Off in development because the dev server is plain http and these would
# make it unusable; they switch on by themselves once DEBUG is False.

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_CONTENT_TYPE_NOSNIFF = True


# Forms

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap4'
CRISPY_TEMPLATE_PACK = 'bootstrap4'


# Rich text editor used for product descriptions
# Two configs: 'default' is the minimal one, kept for short fields; 'extends'
# is the full editor Product.description uses.

CKEDITOR_5_COLOR_PALETTE = [
    {'color': 'hsl(0, 0%, 0%)', 'label': 'Black'},
    {'color': 'hsl(0, 0%, 40%)', 'label': 'Grey'},
    {'color': 'hsl(0, 0%, 100%)', 'label': 'White'},
    {'color': 'hsl(0, 75%, 55%)', 'label': 'Red'},
    {'color': 'hsl(30, 90%, 50%)', 'label': 'Orange'},
    {'color': 'hsl(120, 60%, 35%)', 'label': 'Green'},
    {'color': 'hsl(210, 75%, 50%)', 'label': 'Blue'},
]

CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'heading', '|', 'bold', 'italic', 'link',
            'bulletedList', 'numberedList', 'blockQuote',
        ],
    },
    'extends': {
        'toolbar': [
            'heading', '|', 'outdent', 'indent', '|',
            'bold', 'italic', 'underline', 'strikethrough', 'highlight', '|',
            'fontSize', 'fontFamily', 'fontColor', 'fontBackgroundColor', '|',
            'link', 'bulletedList', 'numberedList', 'todoList', '|',
            'blockQuote', 'codeBlock', 'insertTable', 'imageUpload',
            'mediaEmbed', '|',
            'removeFormat', 'sourceEditing',
        ],
        'blockToolbar': [
            'paragraph', 'heading1', 'heading2', 'heading3', '|',
            'bulletedList', 'numberedList', '|', 'blockQuote',
        ],
        'heading': {
            'options': [
                {'model': 'paragraph', 'title': 'Paragraph',
                 'class': 'ck-heading_paragraph'},
                {'model': 'heading2', 'view': 'h2', 'title': 'Heading 2',
                 'class': 'ck-heading_heading2'},
                {'model': 'heading3', 'view': 'h3', 'title': 'Heading 3',
                 'class': 'ck-heading_heading3'},
            ],
        },
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:alignLeft', 'imageStyle:alignCenter',
                'imageStyle:alignRight',
            ],
            'styles': ['full', 'side', 'alignLeft', 'alignCenter', 'alignRight'],
        },
        'table': {
            'contentToolbar': [
                'tableColumn', 'tableRow', 'mergeTableCells',
                'tableProperties', 'tableCellProperties',
            ],
            'tableProperties': {
                'borderColors': CKEDITOR_5_COLOR_PALETTE,
                'backgroundColors': CKEDITOR_5_COLOR_PALETTE,
            },
            'tableCellProperties': {
                'borderColors': CKEDITOR_5_COLOR_PALETTE,
                'backgroundColors': CKEDITOR_5_COLOR_PALETTE,
            },
        },
        'list': {
            'properties': {
                'styles': True,
                'startIndex': True,
                'reversed': True,
            },
        },
    },
}

CKEDITOR_5_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# imageUpload posts to /ckeditor5/image_upload/. Restrict it to staff — the
# view is reachable by any authenticated user otherwise — and to real image
# types, since the uploads land under MEDIA_ROOT and are served back.
CKEDITOR_5_FILE_UPLOAD_PERMISSION = 'staff'
CKEDITOR_5_UPLOAD_FILE_TYPES = ['jpg', 'jpeg', 'png', 'gif', 'webp']
CKEDITOR_5_MAX_FILE_SIZE = 5  # MB


# Shopping cart

CART_SESSION_ID = 'cart'
