"""Main-host-only template tag; avoids changing shared settings or sibling-site deployments."""

import logging

from django import template
from command_center.mpw_public import public_context

register = template.Library()


@register.simple_tag
def mpw_main_data(request):
    """Keep optional managed content from taking down the public store.

    An unavailable CMS snapshot/database must fail closed to no optional blocks;
    never log exception details, customer data, or private file paths.
    """
    try:
        return public_context(request)
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "MojPlayWin optional managed content unavailable: %s",
            type(exc).__name__,
        )
        return {"mpw_managed_blocks": [], "mpw_managed_offers": []}
