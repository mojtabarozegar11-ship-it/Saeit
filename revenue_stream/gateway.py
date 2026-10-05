"""Official Zarinpal v4 protocol; no payment initiated by tests or readiness checks."""
import json, re, urllib.request

class GatewayError(RuntimeError): pass

class Zarinpal:
    def __init__(self, merchant, sandbox=False):
        self.merchant=merchant
        self.base='https://sandbox.zarinpal.com' if sandbox else 'https://payment.zarinpal.com'

    def _post(self, action, data):
        request=urllib.request.Request(self.base+'/pg/v4/payment/'+action+'.json',
            data=json.dumps(dict(data,merchant_id=self.merchant)).encode(),headers={'Content-Type':'application/json','Accept':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                if response.geturl()!=request.full_url: raise GatewayError('unexpected_redirect')
                value=json.loads(response.read(65536))
            if not isinstance(value,dict) or not isinstance(value.get('data'),dict): raise GatewayError('invalid_response')
            return value['data']
        except (ValueError,OSError) as e: raise GatewayError('provider_unavailable') from e

    def create(self, amount, oid, callback):
        d=self._post('request',{'amount':amount,'currency':'IRR','description':'Zomorod CostKit '+oid,'callback_url':callback})
        authority=d.get('authority','')
        if d.get('code')!=100 or not re.fullmatch('[A-Za-z0-9-]{30,64}',authority): raise GatewayError('request_rejected')
        return authority

    def verify(self, authority, amount):
        d=self._post('verify',{'amount':amount,'authority':authority})
        if d.get('code') not in (100,101) or not re.fullmatch('[0-9]{1,40}',str(d.get('ref_id',''))): raise GatewayError('verification_rejected')
        return {'code':d['code'],'reference':str(d['ref_id'])}

    def url(self, authority):
        if not re.fullmatch('[A-Za-z0-9-]{30,64}',authority): raise GatewayError('invalid_authority')
        return self.base+'/pg/StartPay/'+authority
