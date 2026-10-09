from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .brand import brand_for_request
from .mojplaywin_section_catalog import SECTIONS


@require_GET
def section_page(request, section):
    brand = brand_for_request(request)
    if not brand or brand.code != 'mojplaywin':
        raise Http404
    info = SECTIONS.get(section)
    if info is None:
        raise Http404
    page = {
        'title': info['title'],
        'headline': info['title'],
        'kicker': 'MOJPLAYWIN / EXPLORE',
        'body': info['description'],
        'cards': info['cards'],
    }
    response = render(request, 'brands/mojplaywin/page.html', {
        'brand': brand, 'page': page, 'page_key': section,
    })
    # Hold new sections out of search indexes until editorial review and approval.
    response['X-Robots-Tag'] = 'noindex, follow'
    return response
