import logging

from django.http import HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


def allow_railway_origin(get_response):
    def middleware(request):
        origin = request.META.get('HTTP_ORIGIN', '')
        allowed_origins = {
            'https://myfundihub.com',
            'https://www.myfundihub.com',
            'https://api.myfundihub.com',
            'https://myfundihubback-production.up.railway.app',
        }
        railway_domain = request.META.get('HTTP_HOST', '')
        if railway_domain:
            if railway_domain.startswith('myfundihubfront'):
                allowed_origins.add(f'https://{railway_domain}')
            if railway_domain.startswith('myfundihubback'):
                allowed_origins.add(f'https://{railway_domain}')

        if request.method == 'OPTIONS':
            response = HttpResponse(status=204)
            if origin in allowed_origins or request.path.startswith('/api/'):
                request_headers = request.META.get('HTTP_ACCESS_CONTROL_REQUEST_HEADERS', '')
                response['Access-Control-Allow-Origin'] = origin or 'https://myfundihub.com'
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Headers'] = request_headers or 'Content-Type, Authorization, X-Requested-With, X-Access-Token, X-Auth-Token'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Access-Control-Max-Age'] = '86400'
                response['Vary'] = 'Origin'
            return response

        try:
            response = get_response(request)
        except Exception:
            logger.exception('Unhandled exception while processing %s %s', request.method, request.path)
            response = JsonResponse({'ok': False, 'message': 'Internal server error.'}, status=500)

        if origin in allowed_origins or request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = origin or 'https://myfundihub.com'
            response['Vary'] = 'Origin'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With, X-Access-Token, X-Auth-Token'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'

        return response

    return middleware
