from django.conf import settings
from .models import PlatformSettings

class RateLimited(Exception):
    pass

def acquire_lookup():
    if settings.CELERY_TASK_ALWAYS_EAGER:
        return
    import redis
    config,_=PlatformSettings.objects.get_or_create(pk=1)
    script = """
    local now = redis.call('TIME')
    local key = KEYS[1] .. ':' .. now[1]
    local count = redis.call('INCR', key)
    if count == 1 then redis.call('EXPIRE', key, 2) end
    return count <= tonumber(ARGV[1]) and 1 or 0
    """
    try:
        granted=redis.Redis.from_url(settings.CELERY_BROKER_URL,socket_timeout=3).eval(script,1,'callverify:lookup:rate',config.lookup_rate)
    except redis.RedisError:
        raise RateLimited('Rate limiter unavailable')
    if not granted:
        raise RateLimited('Rate limit reached')
