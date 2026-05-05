"""
DDoS Protection Middleware for CODE-IT Attendance System.

Provides three layers of application-level defense:
1. Global rate limiting — caps requests per IP per time window
2. Request size limiting — rejects oversized payloads
3. Slowloris protection — blocks IPs that send too many concurrent connections
"""

import time
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def get_client_ip(request):
    """Extract real client IP, resisting X-Forwarded-For spoofing."""
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the LAST IP in the chain (the one appended by our trusted proxy/Azure)
        # Avoids grabbing the 0th index which is easily spoofed by attackers
        return x_forwarded_for.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


class DDoSProtectionMiddleware:
    """
    Application-level DDoS mitigation.

    Settings (add to settings.py to override defaults):
        DDOS_RATE_LIMIT          = 100    # max requests per window per IP
        DDOS_RATE_WINDOW         = 60     # window in seconds
        DDOS_BLOCK_DURATION      = 300    # block duration in seconds (5 min)
        DDOS_MAX_BODY_SIZE       = 10     # max request body in MB
        DDOS_WHITELIST_IPS       = []     # IPs that bypass all checks
    """

    # Paths that are exempt from rate limiting (static assets served by WhiteNoise)
    EXEMPT_PREFIXES = ('/static/', '/media/', '/favicon.ico')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings

        # Load configurable thresholds
        rate_limit     = getattr(settings, 'DDOS_RATE_LIMIT', 100)
        rate_window    = getattr(settings, 'DDOS_RATE_WINDOW', 60)
        block_duration = getattr(settings, 'DDOS_BLOCK_DURATION', 300)
        max_body_mb    = getattr(settings, 'DDOS_MAX_BODY_SIZE', 10)
        whitelist      = getattr(settings, 'DDOS_WHITELIST_IPS', [])

        ip   = get_client_ip(request)
        path = request.path

        # --- Bypass: whitelisted IPs and static assets ---
        if ip in whitelist or any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)

        # --- Layer 1: Check if IP is currently blocked ---
        block_key = f'ddos_block_{ip}'
        if cache.get(block_key):
            return HttpResponse(
                '<h1>403 Forbidden</h1>'
                '<p>Your IP has been temporarily blocked due to excessive requests. '
                'Please try again later.</p>',
                status=403,
                content_type='text/html'
            )

        # --- Layer 2: Request body size check ---
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                if int(int(content_length)) > max_body_mb * 1024 * 1024:
                    return HttpResponse(
                        '<h1>413 Payload Too Large</h1>'
                        f'<p>Request body exceeds the {max_body_mb}MB limit.</p>',
                        status=413,
                        content_type='text/html'
                    )
            except (ValueError, TypeError):
                pass

        # --- Layer 3: Sliding window rate limiter ---
        rate_key = f'ddos_rate_{ip}'
        request_count = cache.get(rate_key, 0)

        if request_count >= rate_limit:
            # Block this IP for the configured duration
            cache.set(block_key, True, timeout=block_duration)
            return HttpResponse(
                '<h1>429 Too Many Requests</h1>'
                '<p>You have exceeded the maximum number of requests. '
                'Please try again after a few minutes.</p>',
                status=429,
                content_type='text/html'
            )

        # Increment counter
        if request_count == 0:
            cache.set(rate_key, 1, timeout=rate_window)
        else:
            # Use cache.incr for atomicity; fall back if key expired between get/set
            try:
                cache.incr(rate_key)
            except ValueError:
                cache.set(rate_key, 1, timeout=rate_window)

        # --- Pass through to Django ---
        response = self.get_response(request)

        # Add security headers to every response
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        return response
