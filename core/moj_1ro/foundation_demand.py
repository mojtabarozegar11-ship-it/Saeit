"""Public opportunity discovery. Web content is evidence, never instructions."""
from __future__ import annotations
import hashlib, re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

INTENT = ('request for proposal', 'request for quotation', 'rfp', 'rfq',
          'tender', 'solicitation', 'seeking', 'procurement notice',
          'invitation to bid', 'expression of interest')
NEED = ('automation', 'workflow', 'artificial intelligence', 'software',
        'consulting', 'audit', 'process improvement', 'digital transformation')
BLOCKED = ('login', 'signin', 'register', 'logout', 'javascript:', 'mailto:')

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.links = [], []
        self.anchor, self.hidden = None, 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'a' and not self.hidden:
            self.anchor = [attrs.get('href', ''), []]
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag == 'a' and self.anchor:
            self.links.append((self.anchor[0], ' '.join(self.anchor[1])))
            self.anchor = None
    def handle_data(self, data):
        if self.hidden:
            return
        self.parts.append(data)
        if self.anchor:
            self.anchor[1].append(data)

def matches(text, terms):
    low = text.lower()
    return [t for t in terms if re.search(r'(?<!\w)' + re.escape(t) + r'(?!\w)', low)]

def analyse(body, url, offer, is_detail=False):
    page = Page()
    page.feed(body)
    text = re.sub(r'\s+', ' ', ' '.join(page.parts)).strip()
    links = []
    host = urlparse(url).hostname
    for href, title in page.links:
        target = urljoin(url, href).split('#')[0]
        parsed = urlparse(target)
        if (parsed.scheme != 'https' or parsed.hostname != host or
                parsed.username or parsed.password or
                any(x in target.lower() for x in BLOCKED) or target == url):
            continue
        project = host == 'www.freelancer.com' and parsed.path.startswith('/projects/')
        if host == 'www.freelancer.com' and not project:
            continue
        intent, need = matches(title, INTENT), matches(title, NEED)
        if (project and len(title.strip()) >= 12) or intent or need:
            links.append({'url': target, 'title': title[:300],
                          'priority': 0 if project else (1 if intent and need else 2)})
    unique = {x['url']: x for x in links}
    links = sorted(unique.values(), key=lambda x: (x['priority'], x['url']))[:12]
    from .demand_source_registry import DOMAIN_TERMS
    offer_terms = DOMAIN_TERMS.get(offer.get('type'), DOMAIN_TERMS['ai_automation'])
    intent, need = matches(text, INTENT), matches(text, offer_terms)
    # A listing with general vocabulary is not a specific customer opportunity.
    candidate = None
    project_request = (host == 'www.freelancer.com' and urlparse(url).path.startswith('/projects/')
                       and bool(matches(text, ('project details', 'budget')))
                       and bool(matches(text, ('bid', 'bids', 'proposal'))))
    if is_detail and (intent or project_request) and need:
        title = next((t for _, t in page.links if matches(t, NEED)), '')
        excerpt = text[:2000]
        candidate = {'url': url, 'title': title[:300] or 'Opportunity requires review',
                     'intent_terms': intent or ['public_project_request'], 'need_terms': need,
                     'excerpt': excerpt, 'product_id': offer['id'],
                     'qualification': 'unverified_opportunity',
                     'source_sha256': hashlib.sha256(body.encode()).hexdigest(),
                     'verified_buyer': False}
    candidates = []
    if host == 'www.freelancer.com' and not is_detail:
        for link in links:
            title = re.sub(r'\s+', ' ', link['title']).strip()
            position = text.find(title)
            excerpt = text[position:position + 1600] if position >= 0 else ''
            relevant_need = matches(excerpt, offer_terms)
            active_request = re.search(r'\b\d+\s+(?:days?|hours?|minutes?)\s+left\b', excerpt[:300], re.I)
            if active_request and relevant_need:
                candidates.append({'url': link['url'], 'title': title,
                    'intent_terms': ['public_active_project_request'],
                    'need_terms': relevant_need, 'excerpt': excerpt,
                    'product_id': offer['id'], 'qualification': 'unverified_opportunity',
                    'source_url': url, 'source_sha256': hashlib.sha256(body.encode()).hexdigest(),
                    'verified_buyer': False, 'source_kind': 'public_listing_excerpt'})
    return {'links': links, 'candidate': candidate, 'candidates': candidates,
            'relevant': bool(need), 'intent_terms': intent, 'need_terms': need,
            'source_sha256': hashlib.sha256(body.encode()).hexdigest()}

def proposal(candidate, offer):
    """Draft only. No provider account use, contact, submission or order creation."""
    return {'opportunity_url': candidate['url'], 'product_id': offer['id'],
            'product_title': offer['title'], 'listed_price': offer['price'],
            'currency': offer['currency'], 'evidence_excerpt': candidate['excerpt'],
            'status': 'draft_requires_fit_and_terms_review', 'sent': False,
            'scope': 'Assess this request against the listed automation audit service.',
            'checks_required': ['buyer_identity', 'deadline', 'eligibility',
                                'scope_fit', 'delivery_capacity', 'provider_terms']}
