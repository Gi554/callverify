"""Separate provider evidence: validity never implies an answered call."""
from .models import LookupCheck, CallAttempt

def technical_results(prospect):
    check = LookupCheck.objects.filter(campaign=prospect.campaign, phone=prospect.phone).order_by('-created_at','-pk').first() if prospect.phone else None
    lookup = 'not_checked'
    raw_status = ''
    if check:
        if check.status == 'error':
            lookup = 'error'
        elif check.status == 'completed':
            value = check.response.get('valid')
            lookup = 'invalid' if value is False else 'valid' if value is True else 'unknown'
            package = check.response.get('line_status') or {}
            if isinstance(package, dict) and not package.get('error_code'):
                raw_status = str(package.get('status') or '')
                if value is True and raw_status.lower() == 'reachable':
                    lookup = 'potentially_reachable'
                elif value is True and raw_status.lower() == 'unreachable':
                    lookup = 'unreachable'
    attempt = CallAttempt.objects.filter(prospect=prospect).order_by('-created_at','-pk').first()
    return {'lookup_classification':lookup, 'lookup_line_status':raw_status,
        'lookup_error':check.error if check else '',
        'lookup_checked_at':(check.checked_at.isoformat() if check and check.checked_at else ''),
        'voice_status':attempt.status if attempt else 'not_called',
        'voice_rang':bool(attempt and attempt.rang_at),
        'voice_answered':bool(attempt and attempt.answered_at),
        'voice_amd':attempt.amd if attempt and attempt.amd_requested else 'not_requested',
        'voice_error_code':attempt.error_code if attempt else '',
        'voice_checked_at':attempt.updated_at.isoformat() if attempt else ''}
