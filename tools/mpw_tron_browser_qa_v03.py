"""Local-only Chromium QA with simulated wallet: NEVER sends funds."""
import contextlib
import os
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch

from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mpw_tron_pro.webapp import render_checkout, ASSETS
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tests'))
from test_mpw_tron_pro import A1,A2,SUN

# All live-looking data is SYNTHETIC and only served to the loopback browser QA.
NOW=int(time.time()*1000)
INVOICE={'product_title':'Digital Game Collection','usd':'4.00','amount_sun':SUN,
         'address':A1,'expires_ms':NOW+600000,'status':'pending',
         'monitoring':'not_configured'}
TEST_TOKEN='Z'*48

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlsplit(self.path).path
        if path == '/': content=render_checkout(None,preview=True); mime='text/html; charset=utf-8'
        elif path == '/mock-live': content=render_checkout(INVOICE,token=TEST_TOKEN); mime='text/html; charset=utf-8'
        elif path in ('/assets/checkout.css','/assets/checkout.js'):
            content=(ASSETS/path.split('/')[-1]).read_bytes();mime='text/css' if path.endswith('.css') else 'application/javascript'
        else:
            self.send_response(404);self.end_headers();return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def log_message(self,*args):pass


def stripped_html(raw):
    return raw.replace('<link rel="stylesheet" href="/assets/checkout.css">','').replace('<script src="/assets/checkout.js" defer></script>','')


def main():
    root=Path(__file__).resolve().parents[1]
    css=(ASSETS/'checkout.css').read_text()
    js=(ASSETS/'checkout.js').read_text()
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        for width,height,out in [(390,844,'preview-mobile-v03.png'),(1440,960,'preview-desktop-v03.png')]:
            page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            issues=[];page.on('pageerror',lambda exc:issues.append(str(exc)))
            page.set_content(stripped_html(render_checkout(None,preview=True).decode()),wait_until='load')
            page.add_style_tag(content=css)
            page.add_script_tag(content=js)
            page.screenshot(path=str(root/out),full_page=True)
            assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'),f'{width} horizontal overflow'
            assert not issues, issues
            assert page.locator('#trust-wallet-pay').get_attribute('aria-disabled')=='true'
            assert page.locator('#tronlink-pay').is_disabled()
            results.append(f'preview_{width}px: PASS no-overflow; no page errors; funds-disabled')
            page.close()

        # Isolated synthetic transfer with mocked wallet. No RPC or real network.
        mock_js='''
            window.__calls={signed:0,broadcast:0};
            const recipient="__A1__",sender="__A2__";
            const toHex=a=>a===recipient?"41"+"0".repeat(38)+"65":"41"+"0".repeat(38)+"ca";
            window.fetch=async (url)=>({ok:true,status:200,json:async ()=>url.includes('/api/verify/')?{status:'pending',message:'Mock RPC'}:{status:'pending',monitoring:'not_configured'}});
            window.tron={isTronLink:true,request:async ({method})=>method==='eth_chainId'?'0x2b6653dc':[sender],
                tronWeb:{defaultAddress:{base58:sender},address:{toHex},
                    transactionBuilder:{sendTrx:async (to,amount,from)=>({txID:'a'.repeat(64),raw_data:{contract:[{type:'TransferContract',parameter:{value:{to_address:toHex(to),owner_address:toHex(from),amount}}}]}})},
                    trx:{sign:async tx=>{window.__calls.signed++;return {...tx,signature:['mock']};},sendRawTransaction:async()=>{window.__calls.broadcast++;return {result:true};}}}};
        '''
        mock_js=mock_js.replace('__A1__',A1).replace('__A2__',A2)
        page=browser.new_page(viewport={'width':1280,'height':900})
        errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.set_content(stripped_html(render_checkout(INVOICE,token=TEST_TOKEN).decode()))
        page.add_style_tag(content=css)
        page.evaluate(mock_js)
        page.add_script_tag(content=js)
        assert page.locator('#tronlink-pay').is_enabled()
        assert 'asset=c195' in page.locator('#trust-wallet-pay').get_attribute('href')
        page.click('#tronlink-pay')
        page.locator('.payment-status[data-status="checking"]').wait_for(timeout=3000)
        calls=page.evaluate('window.__calls')
        assert calls=={'signed':1,'broadcast':1},calls
        assert page.locator('#txid').input_value()=='a'*64
        assert page.locator('.status-label').text_content()=='CHECKING'
        assert not errors, errors
        results.append('mock_wallet_payment: PASS one user-authorized sign + broadcast, not falsely PAID')
        page.close()

        page=browser.new_page(viewport={'width':390,'height':844})
        page.set_content(stripped_html(render_checkout(INVOICE,token=TEST_TOKEN).decode()))
        page.add_style_tag(content=css)
        page.evaluate(mock_js.replace("'0x2b6653dc'", "'0x94a9059e'"))
        page.add_script_tag(content=js)
        page.click('#tronlink-pay')
        page.wait_for_timeout(80)
        assert page.evaluate('window.__calls')=={'signed':0,'broadcast':0}
        assert 'Switch your wallet to TRON Mainnet' in page.locator('#feedback').text_content()
        results.append('mock_wrong_chain: PASS blocked before signing/broadcast')
        page.close()

        # The buyer must see distinct final TRON payment and merchant delivery.
        page=browser.new_page(viewport={'width':390,'height':844})
        errors=[];page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(stripped_html(render_checkout(INVOICE,token=TEST_TOKEN).decode()))
        page.add_style_tag(content=css)
        page.evaluate('''window.fetch=async()=>({ok:true,status:200,json:async()=>({status:'paid',payment_confirmed:true,fulfillment:'delivered',txid:'a'.repeat(64),monitoring:'running'})});''')
        page.add_script_tag(content=js)
        page.wait_for_function("document.getElementById('fulfillment-notice').dataset.status === 'delivered'",timeout=3500)
        assert page.locator('#stage-done').get_attribute('class').find('done')>=0
        assert page.locator('#tronlink-pay').is_disabled()
        assert 'Digital delivery confirmed' in page.locator('#fulfillment-notice').text_content()
        assert not errors,errors
        results.append('mock_fulfilled_order: PASS payment-finality and merchant-delivery shown separately; no double-send')
        page.close()
        browser.close()
    print('\n'.join(results))
    (root/'browser_qa_results.txt').write_text('\n'.join(results)+'\n')

if __name__=='__main__':main()