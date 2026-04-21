import uuid
from .models import ActivityLog, Admin

def log_activity(request, action, target=None, description=None):
    """
    Utility function to log administrative actions.
    Records the admin performing the action, the target of the action,
    and a description.
    """
    admin_id = request.session.get('admin_id')
    admin = None
    if admin_id:
        try:
            admin = Admin.objects.get(id=admin_id)
        except Admin.DoesNotExist:
            pass
    
    # IP Address logging removed as per user request (Privacy)

    ActivityLog.objects.create(
        id=uuid.uuid4(),
        admin=admin,
        action=action,
        target=target,
        description=description
    )

from django.core.cache import cache

def get_client_ip(request):
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the LAST IP added by the trusted proxy, not the first spoofable one
        ip = x_forwarded_for.split(',')[-1].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return ip

def is_ip_locked(ip):
    return cache.get(f'login_fail_{ip}', 0) >= 5

def track_login_failure(ip):
    key = f'login_fail_{ip}'
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=900)  # 15 minutes lockout

def clear_login_failures(ip):
    cache.delete(f'login_fail_{ip}')

def verify_password(raw_password: str, stored_hash: str) -> bool:
    """Verifies a password against either raw SHA-256 or PBKDF2 formats"""
    if not stored_hash:
        return False
    # Legacy SHA-256 verification (exactly 64 hex characters)
    if len(stored_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in stored_hash):
        import hashlib
        return hashlib.sha256(raw_password.encode()).hexdigest() == stored_hash
    # New Django hash verification
    from django.contrib.auth.hashers import check_password
    return check_password(raw_password, stored_hash)
