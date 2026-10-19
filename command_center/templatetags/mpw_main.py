"""Main-host-only template tag; avoids changing shared settings or sibling-site deployments."""
from django import template
from command_center.mpw_public import public_context

register = template.Library()


@register.simple_tag
def mpw_main_data(request):
    return public_context(request)
