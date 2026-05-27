import hashlib
import re
import secrets

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail


OTP_TTL_SECONDS = 10 * 60
OTP_LOCK_SECONDS = 30 * 60
OTP_MAX_ATTEMPTS = 5
RESET_REQUEST_LIMIT = 3
RESET_REQUEST_WINDOW_SECONDS = 20 * 60
PASSWORD_SPECIAL_RE = re.compile(r'[!@#$%^&*(),.?":{}|<>]')


def normalize_email(email):
    return (email or '').strip().lower()


def normalize_otp(value):
    digits = re.sub(r'\D', '', value or '')
    if len(digits) == 7:
        return f'{digits[:3]}-{digits[3:]}'
    return value.strip()


def generate_otp():
    return f'{secrets.randbelow(1000):03d}-{secrets.randbelow(10000):04d}'


def _hash_key(value):
    return hashlib.sha256((value or '').encode()).hexdigest()[:32]


def reset_key(kind, email, ip):
    return f'pw_reset:{kind}:{_hash_key(normalize_email(email))}:{_hash_key(ip)}'


def reset_lock_key(kind, email, ip):
    return f'{reset_key(kind, email, ip)}:locked'


def reset_request_key(kind, ip):
    return f'pw_reset_requests:{kind}:{_hash_key(ip)}'


def is_reset_locked(kind, email, ip):
    return bool(cache.get(reset_lock_key(kind, email, ip)))


def is_reset_request_limited(kind, ip):
    return (cache.get(reset_request_key(kind, ip)) or 0) >= RESET_REQUEST_LIMIT


def record_reset_request(kind, ip):
    key = reset_request_key(kind, ip)
    current = cache.get(key, 0)
    cache.set(key, current + 1, timeout=RESET_REQUEST_WINDOW_SECONDS)
    return current + 1


def store_reset_otp(kind, email, ip, otp, account_id=''):
    cache.set(
        reset_key(kind, email, ip),
        {'otp': otp, 'attempts': 0, 'account_id': str(account_id or '')},
        timeout=OTP_TTL_SECONDS,
    )


def get_reset_state(kind, email, ip):
    return cache.get(reset_key(kind, email, ip)) or {}


def clear_reset_state(kind, email, ip):
    cache.delete(reset_key(kind, email, ip))
    cache.delete(reset_lock_key(kind, email, ip))


def record_bad_otp(kind, email, ip):
    key = reset_key(kind, email, ip)
    state = cache.get(key) or {'attempts': 0}
    attempts = int(state.get('attempts') or 0) + 1
    state['attempts'] = attempts
    cache.set(key, state, timeout=OTP_TTL_SECONDS)
    if attempts >= OTP_MAX_ATTEMPTS:
        cache.set(reset_lock_key(kind, email, ip), True, timeout=OTP_LOCK_SECONDS)
        cache.delete(key)
        return True
    return False


def validate_new_password(password, confirm):
    if len(password or '') < 8:
        return 'Password must be at least 8 characters.'
    if not PASSWORD_SPECIAL_RE.search(password or ''):
        return 'Password must contain at least one special character.'
    if password != confirm:
        return 'Passwords do not match.'
    return ''


def send_password_reset_otp(email, otp, label):
    if not email:
        return
    send_mail(
        f'CODE-IT {label} Password Reset OTP',
        (
            f'Your CODE-IT password reset OTP is {otp}.\n\n'
            'This code expires in 10 minutes. If you did not request this, you can ignore this email.'
        ),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=True,
    )
