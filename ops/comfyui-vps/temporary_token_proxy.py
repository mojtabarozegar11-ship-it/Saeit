#!/usr/bin/env python3
"""Short-lived, authenticated HTTP/WebSocket proxy for an isolated ComfyUI.

Only the SHA-256 digest of a 256-bit random access token is versioned.
The token itself is never stored in this repository or in public Actions logs.
Use exclusively behind a time-limited HTTPS tunnel, bound to loopback.
"""
import asyncio
import hashlib
import hmac
import os
from urllib.parse import urlsplit

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

DIGEST = "3a0601107f597ee44abb9d63d2db54558fc8d2c40de3dcde12cadd15e4f20d97"
COOKIE = "__Host-comfy-session"
UPSTREAM = "http://127.0.0.1:18188"
HOST = "127.0.0.1"
PORT = 18189
HOP = {"host", "connection", "keep-alive", "proxy-authenticate",
       "proxy-authorization", "te", "trailer", "transfer-encoding",
       "upgrade", "cookie", "content-length", "sec-websocket-key",
       "sec-websocket-version", "sec-websocket-extensions",
       "sec-websocket-protocol"}
RETURN_HOP = {"connection", "keep-alive", "proxy-authenticate",
              "proxy-authorization", "te", "trailer", "transfer-encoding",
              "upgrade", "set-cookie"}


def match_token(token: str) -> bool:
    if len(token) < 40 or len(token) > 256:
        return False
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, DIGEST)


def headers(request):
    result = {key: val for key, val in request.headers.items() if key.lower() not in HOP}
    result["X-Forwarded-Proto"] = "https"
    return result


@web.middleware
async def gate(request, handler):
    if request.path == "/_relay_live":
        return web.Response(text="ok", headers={"Cache-Control": "no-store"})
    if request.path == "/enter":
        token = request.query.get("key", "")
        if not match_token(token):
            return web.Response(status=403, text="Access denied")
        resp = web.HTTPSeeOther(location="/")
        resp.set_cookie(COOKIE, token, secure=True, httponly=True,
                        samesite="Strict", path="/", max_age=3600)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Referrer-Policy"] = "no-referrer"
        raise resp
    if not match_token(request.cookies.get(COOKIE, "")):
        return web.Response(
            status=401,
            text="Private ComfyUI session. Open your authorized access link.",
            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
        )
    return await handler(request)


async def start_client(app):
    app["client"] = ClientSession(
        timeout=ClientTimeout(total=None, sock_connect=10, sock_read=None),
        auto_decompress=False,
        trust_env=False,
    )


async def stop_client(app):
    await app["client"].close()


async def forward_ws(request):
    client = request.app["client"]
    downstream = web.WebSocketResponse(heartbeat=20, max_msg_size=0)
    await downstream.prepare(request)
    target = UPSTREAM.replace("http:", "ws:", 1) + str(request.rel_url)
    try:
        async with client.ws_connect(target, heartbeat=20, max_msg_size=0, headers=headers(request)) as upstream:
            async def to_upstream():
                async for msg in downstream:
                    if msg.type == WSMsgType.TEXT:
                        await upstream.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await upstream.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
            async def to_downstream():
                async for msg in upstream:
                    if msg.type == WSMsgType.TEXT:
                        await downstream.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await downstream.send_bytes(msg.data)
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
            tasks = [asyncio.create_task(to_upstream()), asyncio.create_task(to_downstream())]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        pass
    finally:
        await downstream.close()
    return downstream


async def forward_http(request):
    client = request.app["client"]
    url = UPSTREAM + str(request.rel_url)
    data = request.content if request.method not in ("GET", "HEAD") else None
    try:
        async with client.request(request.method, url, data=data,
                                  headers=headers(request), allow_redirects=False) as upstream:
            filtered = {k: v for k, v in upstream.headers.items()
                        if k.lower() not in RETURN_HOP}
            response = web.StreamResponse(status=upstream.status, headers=filtered)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["X-Content-Type-Options"] = "nosniff"
            await response.prepare(request)
            if request.method != "HEAD":
                async for chunk in upstream.content.iter_chunked(65536):
                    await response.write(chunk)
            await response.write_eof()
            return response
    except (ConnectionError, TimeoutError, OSError):
        return web.Response(status=503, text="ComfyUI is offline. Start a bounded VPS session from GitHub Actions.")


async def relay(request):
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return await forward_ws(request)
    return await forward_http(request)


app = web.Application(middlewares=[gate], client_max_size=64 * 1024 * 1024)
app.cleanup_ctx.append(lambda app: _client_lifecycle(app))
app.router.add_route("*", "/{tail:.*}", relay)


async def _client_lifecycle(app):
    await start_client(app)
    yield
    await stop_client(app)


if __name__ == "__main__":
    web.run_app(app, host=HOST, port=PORT, access_log=None, print=None)
