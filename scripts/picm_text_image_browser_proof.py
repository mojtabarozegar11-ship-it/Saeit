#!/usr/bin/env python3
"""Browser proof of actual PICM text-image JS flow; simulated private API only.

A real Chromium exercises: text-only request (no file), CSRF, status polling,
private PNG download, and quota error. Does NOT prove GPU or AI image quality.
"""
import asyncio
import base64
import binascii
from pathlib import Path
import struct
import zlib
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "templates/picm/text_image.js"
JOB_ID = "a" * 32


def make_png():
    def chunk(name, data):
        return (struct.pack(">I", len(data)) + name + data
                + struct.pack(">I", binascii.crc32(name + data) & 0xffffffff))
    size = 256
    raw = (b"\x00" + b"\x60\x20\xc0" * size) * size
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, level=0))
            + chunk(b"IEND", b""))


HTML = """
<html lang="fa"><body>
<button data-mode="image_edit" type="button">Edit</button>
<button data-mode="text_image" id="choose-text" type="button">AI Image</button>
<button data-mode="image_video" type="button">Video</button>
<div id="capability-notice"></div>
<div id="text-image-options" hidden>
<select id="picm-ai-style"><option value="natural" selected>Natural</option></select>
<select id="picm-ai-steps"><option value="1" selected>One</option></select>
<button id="picm-text-resume" hidden type="button">Resume</button>
</div>
<div id="preview">Preview</div><p id="status"></p>
<form id="renderform">
<input name="csrfmiddlewaretoken" value="test-csrf" type="hidden">
<input id="mode" name="mode" type="hidden" value="image_edit">
<label for="photo">Reference photo</label>
<input id="photo" name="photo" type="file" required>
<p id="photohelp">photo help</p>
<div id="promptgroup">
<label for="prompt">Prompt</label>
<textarea id="prompt" required minlength="4" maxlength="580"></textarea>
</div>
<button id="submit" type="submit">Submit</button>
</form>
</body></html>
"""


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome",headless=True,args=["--no-sandbox"])
        try:
            page = await browser.new_page(accept_downloads=True)
            await page.set_content(HTML)
            await page.evaluate("""() => {
                document.querySelectorAll("[data-mode]").forEach(el =>
                    el.addEventListener("click", () => {
                        document.getElementById("mode").value=el.dataset.mode
                    }));
            }""")
            fixture=base64.b64encode(make_png()).decode("ascii")
            await page.evaluate("""({data, id}) => {
                const binary=atob(data);
                const bytes=Uint8Array.from(binary,c=>c.charCodeAt(0));
                window.proof={requests:[],code:202,bytes,id};
                window.fetch=async (path,options={}) => {
                    window.proof.requests.push({path,method:options.method||"GET",
                        body:options.body||null,csrf:options.headers?.["X-CSRFToken"]||null,
                        credentials:options.credentials||null});
                    if(path==="/picm/api/submit/"){
                        if(window.proof.code!==202)
                            return new Response(JSON.stringify({error:"daily_limit_reached"}),{
                                status:429,headers:{"Content-Type":"application/json"}});
                        return new Response(JSON.stringify({id,state:"queued"}),{
                            status:202,headers:{"Content-Type":"application/json"}});
                    }
                    if(path==="/picm/api/status/"+id+"/")
                        return new Response(JSON.stringify({
                            id,state:"done",image_url:"/picm/image/"+id+"/"
                        }),{status:200,headers:{"Content-Type":"application/json"}});
                    if(path==="/picm/image/"+id+"/")
                        return new Response(window.proof.bytes,{
                            status:200,headers:{"Content-Type":"image/png"}});
                    throw Error("Unexpected private API call "+path);
                };
            }""",{"data":fixture,"id":JOB_ID})
            await page.add_script_tag(content=SCRIPT.read_text(encoding="utf-8"))
            await page.locator("#choose-text").click()
            assert await page.locator("#photo").evaluate("(el) => !el.required && el.hidden")
            assert await page.locator("#text-image-options").evaluate("(el)=>!el.hidden")
            await page.locator("#prompt").fill("A photorealistic sunrise over an emerald field")
            await page.locator("#submit").click()
            await page.locator('a[download^="picm-ai-"]').wait_for(timeout=13000)
            data=await page.evaluate("""async () => {
                const a=document.querySelector('a[download^="picm-ai-"]');
                const png=await (await fetch(a.href)).arrayBuffer();
                const events=window.proof.requests;
                return {
                  name:a.download,
                  bytes:png.byteLength,
                  status:document.querySelector("#status").textContent,
                  resultImage:!!document.querySelector("#preview img"),
                  posted:JSON.parse(events.find(x=>x.path==="/picm/api/submit/").body),
                  requests:events.filter(x=>!x.path.startsWith("blob:"))
                };
            }""")
            assert data["bytes"]>1024,data
            assert data["name"]=="picm-ai-"+JOB_ID+".png",data
            assert data["resultImage"],data
            assert "۲۵۶" in data["status"],data
            assert data["posted"]=={
                "prompt":"A photorealistic sunrise over an emerald field",
                "style":"natural","steps":1,
            },data
            posts=[v for v in data["requests"] if v["path"]=="/picm/api/submit/"]
            assert len(posts)==1 and posts[0]["csrf"]=="test-csrf",data
            assert all(v["credentials"]=="same-origin" for v in data["requests"]),data
            print("PICM_REAL_TEXT_IMAGE_BROWSER_REQUEST_AND_DOWNLOAD_OK")
            # A second request must show a truthful quota error, not fake completion.
            await page.evaluate("window.proof.code=429")
            await page.locator("#submit").click()
            await page.wait_for_function("""() => document.querySelector("#status")
                .textContent.includes("سقف دو تصویر")""",timeout=5000)
            print("PICM_TEXT_IMAGE_QUOTA_ERROR_VISIBLE")
        finally:
            await browser.close()


if __name__=="__main__":
    asyncio.run(main())
