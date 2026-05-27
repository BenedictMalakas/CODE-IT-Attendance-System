import re
from datetime import datetime

from django.utils import timezone

from .models import Event, Section


_SECTION_NUMBER_RE = re.compile(r'(\d+)')


def section_sort_key(section):
    numbers = [int(value) for value in _SECTION_NUMBER_RE.findall(section.name or '')]
    suffix = numbers[-1] if numbers else 0
    return (section.year_level or 0, suffix, section.name.lower())


def sorted_sections(queryset=None):
    if queryset is None:
        queryset = Section.objects.all()
    return sorted(list(queryset), key=section_sort_key)


def auto_update_event_statuses(now=None):
    now_local = timezone.localtime(now or timezone.now())
    today = now_local.date()
    current_tz = timezone.get_current_timezone()
    updated = {'pending_to_active': 0, 'active_to_ended': 0}

    for event in Event.objects.filter(status='pending'):
        should_activate = event.date < today
        if not should_activate and event.date == today and event.start_time:
            event_start = timezone.make_aware(
                datetime.combine(event.date, event.start_time),
                current_tz,
            )
            should_activate = now_local >= event_start

        if should_activate:
            event.status = 'active'
            event.save(update_fields=['status'])
            updated['pending_to_active'] += 1

    for event in Event.objects.filter(status='active'):
        should_end = event.date < today
        if not should_end and event.date == today and event.end_time:
            event_end = timezone.make_aware(
                datetime.combine(event.date, event.end_time),
                current_tz,
            )
            should_end = now_local >= event_end

        if should_end:
            event.status = 'ended'
            event.save(update_fields=['status'])
            updated['active_to_ended'] += 1

    return updated
