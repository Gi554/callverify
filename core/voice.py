"""Voice observations only. Outbound submissions are deliberately disabled."""

from rest_framework.exceptions import ValidationError
from .models import CallAttempt, CallCampaign

DISABLED_REASON = 'Émission Voice désactivée : validation réglementaire canadienne requise'
AMD_VALUES = {
    'human',
    'machine_start',
    'machine_end_beep',
    'machine_end_silence',
    'machine_end_other',
    'fax',
    'unknown',
}


def prepare_pilot(pk, prospect_ids):
    raise ValidationError(DISABLED_REASON)


def submit_attempt(pk):
    CallAttempt.objects.filter(pk=pk, status__in=['pending', 'queued']).update(status='blocked')


def amd_parameters(enabled, callback_url):
    """Options for a future authorized adapter; never places a call."""
    if not enabled:
        return {}
    from urllib.parse import urlparse

    url = urlparse(callback_url)
    if url.scheme != 'https' or not url.hostname or url.query or url.fragment:
        raise ValidationError('Webhook AMD public HTTPS requis')
    return {
        'machine_detection': 'Enable',
        'async_amd': True,
        'async_amd_status_callback': callback_url,
        'async_amd_status_callback_method': 'POST',
    }


def stop_pilot(pk):
    obj = CallCampaign.objects.get(pk=pk)
    obj.status = 'stopped'
    obj.save(update_fields=['status'])
    CallAttempt.objects.filter(call_campaign=obj, status='pending').update(status='canceled')
    return obj, 0
