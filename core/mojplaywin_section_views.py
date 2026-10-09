from django.http import Http404
from django.shortcuts import render

from .brand import brand_for_request
from .mojplaywin_section_catalog import SECTIONS


def section_page(request, section):
    brand = brand_for_request(request)
    if not brand or brand.code != 'mojplaywin' or section not in SECTIONS:
        raise Http404
    title, description = SECTIONS[section]
    page = {
        'title': title,
        'headline': title,
        'kicker': 'MOJPLAYWIN / EXPLORE',
        'body': description,
        'cards': [
            ('Overview', 'Introduction', 'Explore the fundamentals of ' + title.lower() + '.'),
            ('Research', 'Insights', 'Review concepts, terminology and relevant developments.'),
            ('Resources', 'Learning', 'Discover educational resources as they become available.'),
        ],
    }
    response = render(request, 'brands/mojplaywin/page.html', {'brand': brand, 'page': page, 'page_key': section})
    response['X-Robots-Tag'] = 'noindex, follow'
    return response
