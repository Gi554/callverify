from time import perf_counter

from django.db import connection


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.headers.get('X-Orvia-Timing') != '1':
            return self.get_response(request)
        started = perf_counter()
        sql_time = 0

        def measure(execute, sql, params, many, context):
            nonlocal sql_time
            before = perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                sql_time += perf_counter() - before

        with connection.execute_wrapper(measure):
            response = self.get_response(request)
        elapsed = (perf_counter() - started) * 1000
        response['Server-Timing'] = f'app;dur={elapsed:.1f}, db;dur={sql_time * 1000:.1f}'
        return response
