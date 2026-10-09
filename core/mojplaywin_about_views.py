"""Host-isolated MojPlayWin about page, separate from the company portal."""
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from .brand import brand_for_request


@require_GET
def mojplaywin_about(request):
    brand = brand_for_request(request)
    if getattr(brand, 'code', None) != 'mojplaywin':
        return redirect('company', permanent=True)
    response = render(request, 'brands/mojplaywin/about.html', {'brand': brand})
    response['X-Robots-Tag'] = 'noindex, follow, noarchive'
    response['Cache-Control'] = 'private, no-store'
    return response
