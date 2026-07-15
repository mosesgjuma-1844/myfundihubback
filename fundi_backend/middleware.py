from django.http import HttpResponse


def allow_railway_origin(get_response):
    def middleware(request):
        origin = request.META.get('HTTP_ORIGIN', '')
        allowed_origins = {
            'https://myfundihubfront.up.railway.app',
            'https://myfundihubback.up.railway.app',
            'https://myfundihubfront-production.up.railway.app',
            'https://myfundihubback-production.up.railway.app',
        }
        railway_domain = request.META.get('HTTP_HOST', '')
        if railway_domain:
            if railway_domain.startswith('myfundihubfront'):
                allowed_origins.add(f'https://{railway_domain}')
            if railway_domain.startswith('myfundihubback'):
                allowed_origins.add(f'https://{railway_domain}')

        response = get_response(request)
        if origin in allowed_origins or request.path.startswith('/api/'):
            response['Access-Control-Allow-Origin'] = origin or 'https://myfundihubfront-production.up.railway.app'
            response['Vary'] = 'Origin'
            response['Access-Control-Allow-Credentials'] = 'true'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'

        if request.method == 'OPTIONS':
            response = HttpResponse(status=204)
            if origin in allowed_origins or request.path.startswith('/api/'):
                response['Access-Control-Allow-Origin'] = origin or 'https://myfundihubfront-production.up.railway.app'
                response['Access-Control-Allow-Credentials'] = 'true'
                response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
                response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
                response['Vary'] = 'Origin'
        return response

    return middleware
