"""Prepare actionable customer handoffs without inventing buyers or sending bids."""
from urllib.parse import urlparse


def prepare_handoff(candidate, offer, readiness):
    target = candidate['url']
    parsed = urlparse(target)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('invalid_customer_route')
    marketplace = parsed.hostname == 'www.freelancer.com' and parsed.path.startswith('/projects/')
    missing = list(readiness['missing']) + [
        'buyer_identity_and_current_deadline', 'scope_and_delivery_capacity',
        'customer_acceptance_of_terms', 'verified_payment_and_delivery',
    ]
    missing.append('authenticated_marketplace_account' if marketplace else 'verified_contact_channel')
    return {
        'state': 'review_required', 'product_id': offer['id'],
        'opportunity_url': target,
        'contact_route': {'kind': 'marketplace_project' if marketplace else 'source_review',
                          'url': target, 'connected': False},
        'offer': dict(offer), 'purchasable': readiness['purchasable'],
        'draft_message': (
            'I am reviewing your request for an automation audit. '
            'Could you confirm whether an assessment of the current workflow, '
            'risks and recommended next steps meets your need? '
            'Implementation or takeover of a production system requires separate scoping. '
            'The listed audit price is ' + str(offer['price']) + ' ' + offer['currency'] +
            '; availability and delivery terms must be confirmed before contracting.'
        ),
        'terms_review': {
            'scope': 'Audit assessment; implementation excluded unless separately agreed.',
            'price': str(offer['price']), 'currency': offer['currency'],
            'delivery_deadline': None, 'accepted_by_customer': False,
            'payment_channel': 'must follow the selected platform terms',
        },
        'missing': missing, 'sent': False, 'customer_verified': False,
        'source_sha256': candidate.get('source_sha256'),
    }


def snapshot(c):
    rows = list(c.execute('SELECT * FROM customer_handoffs ORDER BY updated DESC LIMIT 20'))
    return {'prepared': c.execute('SELECT count(*) FROM customer_handoffs').fetchone()[0],
            'sent': 0, 'verified_customers': 0,
            'routes': [{'url': r['url'], 'product_id': r['product_id'],
                        'state': r['state'], 'artifact_path': r['artifact_path']} for r in rows]}
