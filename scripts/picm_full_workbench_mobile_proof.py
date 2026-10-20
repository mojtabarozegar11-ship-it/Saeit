#!/usr/bin/env python3
"""PICM entire production Django template browser integration proof.

No external network. Exercise ALL inline scripts in production order on a
mock HTTPS site, in Chrome desktop AND mobile emulation. Server API responses
are mocked; this tests actual front-end submission, not VPS inference quality.
"""
import asyncio
import binascii
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.test import RequestFactory
from core.picm_views import picm_workbench
from playwright.async_api import async_playwright

JOB_ID="a"*32
URL="https://mojplaywin.com/picm/workspace/"


def png_fixture():
    def c(name,data):
        return (struct.pack(">I",len(data))+name+data+
                struct.pack(">I",binascii.crc32(name+data)&0xffffffff))
    n=256
    raw=(b"\0"+b"\x20\x88\x36"*n)*n
    return (b"\x89PNG\r\n\x1a\n"
            +c(b"IHDR",struct.pack(">IIBBBBB",n,n,8,2,0,0,0))
            +c(b"IDAT",zlib.compress(raw,level=0))+c(b"IEND",b""))


def owner_workbench():
    with tempfile.TemporaryDirectory() as work:
        original=os.environ.get("PICM_STORAGE_DIR")
        os.environ["PICM_STORAGE_DIR"]=work
        try:
            (Path(work)/".owner-user-id").write_text("42\n",encoding="ascii")
            r=RequestFactory().get("/picm/workspace/")
            r.user=SimpleNamespace(pk=42,is_authenticated=True,is_active=True)
            response=picm_workbench(r)
            assert response.status_code==200
            html=response.content.decode("utf-8")
            assert "id=\"mode-text_image\"" in html
            assert 'fetch("/picm/api/submit/"' in html
            # Full real template includes free_motion, story_preview, and text_image.
            assert "MediaRecorder" in html and "story-options" in html
            return html
        finally:
            if original is None: os.environ.pop("PICM_STORAGE_DIR",None)
            else: os.environ["PICM_STORAGE_DIR"]=original


async def scenario(browser, html, mobile=False):
    context=await browser.new_context(
        viewport={"width":390 if mobile else 1200,"height":830},
        device_scale_factor=2 if mobile else 1,
        is_mobile=mobile, has_touch=mobile,
        accept_downloads=True,
        service_workers="block",
    )
    page=await context.new_page()
    events=[]
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    async def route(request):
        url=request.request.url
        if url==URL and request.request.method=="GET":
            await request.fulfill(status=200,body=html,content_type="text/html")
        elif url=="https://mojplaywin.com/picm/api/submit/" and request.request.method=="POST":
            data=request.request.post_data_json
            assert data["prompt"]=="Lush green wheat fields in bright morning sunlight",data
            assert data["steps"]==1,data
            assert data["style"]=="natural",data
            assert request.request.headers.get("x-csrftoken"),"Missing CSRF header"
            events.append(("submit",request.request.method))
            await request.fulfill(status=202,body=json.dumps({"id":JOB_ID,"state":"queued"}),content_type="application/json")
        elif url=="https://mojplaywin.com/picm/api/status/"+JOB_ID+"/":
            events.append(("poll",request.request.method))
            await request.fulfill(status=200,body=json.dumps({"id":JOB_ID,"state":"done","image_url":"/picm/image/"+JOB_ID+"/"}),content_type="application/json")
        elif url=="https://mojplaywin.com/picm/image/"+JOB_ID+"/":
            events.append(("image",request.request.method))
            await request.fulfill(status=200,body=png_fixture(),content_type="image/png")
        else:
            await request.abort()
    await page.route("**/*",route)
    try:
        await page.goto(URL,wait_until="load")
        # Most users land here with no photo. The default must actually be
        # usable before clicking any mode tile.
        first=await page.evaluate("""() => ({
            mode:document.getElementById('mode').value,
            photoRequired:document.getElementById('photo').required,
            photoHidden:document.getElementById('photo').hidden,
            noValidate:document.getElementById('renderform').noValidate,
            button:document.getElementById('submit').textContent
        })""")
        assert first["mode"]=="text_image" and first["photoHidden"] and not first["photoRequired"],first
        assert first["noValidate"] and "ساخت عکس" in first["button"],first
        await page.locator("#submit").click()
        await page.wait_for_function("""() => document.getElementById('status')
            .textContent.includes('متن (۴ تا ۵۸۰')""",timeout=3000)
        assert not events,"Missing prompt must not submit"
        state=await page.evaluate("""() => ({
            mode:document.getElementById('mode').value,
            photoRequired:document.getElementById('photo').required,
            photoHidden:document.getElementById('photo').hidden,
            promptRequired:document.getElementById('prompt').required,
            formValid:document.getElementById('renderform').checkValidity(),
            scripts:document.querySelectorAll('script').length
        })""")
        assert state["mode"]=="text_image",state
        assert not state["photoRequired"] and state["photoHidden"],state
        assert state["promptRequired"],state
        await page.locator("#picm-ai-style").select_option("natural")
        await page.locator("#picm-ai-steps").select_option("1")
        await page.locator("#prompt").fill("Lush green wheat fields in bright morning sunlight")
        validity=await page.locator("#renderform").evaluate("(form) => ({valid:form.checkValidity(), errors:Array.from(form.querySelectorAll(':invalid')).map(x=>x.id)})")
        assert validity["valid"],validity
        await page.locator("#submit").click()
        await page.locator('a[download^="picm-ai-"]').wait_for(state="attached",timeout=14000)
        assert events==[("submit","POST"),("poll","GET"),("image","GET")],events
        link=page.locator('a[download^="picm-ai-"]')
        assert await link.get_attribute("download")=="picm-ai-"+JOB_ID+".png"
        assert not errors,errors
        print("PICM_FULL_WORKBENCH_MOBILE_OK" if mobile else "PICM_FULL_WORKBENCH_DESKTOP_OK")
        print("PICM_OWNER_FORM_SUBMIT_ACTUAL_HTTP_REQUEST_SIMULATED_OK")
    finally:
        await context.close()


async def main():
    html=owner_workbench()
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox"])
        try:
            await scenario(browser,html,False)
            await scenario(browser,html,True)
        finally:
            await browser.close()


if __name__=="__main__":
    asyncio.run(main())
