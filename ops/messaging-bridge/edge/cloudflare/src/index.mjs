/**
 * Private WhatsApp WebSocket egress experiment.
 * It is not an open proxy: only the WhatsApp Web chat endpoint is permitted.
 * No account sessions, credentials or message bodies are logged or persisted.
 * Deploy only after validating Cloudflare account eligibility and policy.
 */
const UPSTREAM = 'https://web.whatsapp.com/ws/chat';

function sameSecret(actual, expected) {
  if (!actual || !expected || typeof actual !== 'string' || typeof expected !== 'string') return false;
  const a = new TextEncoder().encode(actual);
  const b = new TextEncoder().encode(expected);
  if (a.length !== b.length || a.length < 32) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a[i] ^ b[i];
  return difference === 0;
}

function closeSafely(socket, code = 1000) {
  try {
    if (socket.readyState === 0 || socket.readyState === 1) socket.close(code);
  } catch {
    // Connection is already closed.
  }
}

function couple(left, right) {
  const forward = (from, to) => {
    from.addEventListener('message', event => {
      try {
        if (to.readyState === 1) to.send(event.data);
        else closeSafely(from, 1011);
      } catch {
        closeSafely(from, 1011);
        closeSafely(to, 1011);
      }
    });
    from.addEventListener('close', () => closeSafely(to));
    from.addEventListener('error', () => {
      closeSafely(from, 1011);
      closeSafely(to, 1011);
    });
  };
  forward(left, right);
  forward(right, left);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === 'GET' && url.pathname === '/health') {
      return new Response(JSON.stringify({ ready: true, type: 'whatsapp-websocket-egress' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }
      });
    }
    // A private path token is supported for clients that cannot attach a
    // WebSocket-only header. It must be high entropy and never appear in logs.
    const privatePath = /^\/bridge\/([A-Za-z0-9_-]{43,128})\/ws\/chat$/.exec(url.pathname);
    if (request.method !== 'GET' || (url.pathname !== '/ws/chat' && !privatePath)) {
      return new Response('Not found', { status: 404 });
    }
    const suppliedSecret = request.headers.get('X-Moj-Bridge-Token') || privatePath?.[1];
    if (!sameSecret(suppliedSecret, env?.BRIDGE_SHARED_TOKEN)) {
      return new Response('Unauthorized', { status: 401, headers: { 'Cache-Control': 'no-store' } });
    }
    if (request.headers.get('Upgrade')?.toLowerCase() !== 'websocket') {
      return new Response('WebSocket upgrade required', { status: 426 });
    }

    // Baileys may append ED routing information to its WebSocket URL after
    // authentication. Forward only this supported parameter, never arbitrary URLs.
    const upstreamUrl = new URL(UPSTREAM);
    const routing = url.searchParams.get('ED');
    if (routing) {
      if (routing.length > 4096) return new Response('Invalid routing data', { status: 400 });
      upstreamUrl.searchParams.set('ED', routing);
    }

    let upstreamResponse;
    try {
      upstreamResponse = await fetch(upstreamUrl.toString(), {
        headers: { Upgrade: 'websocket', Origin: 'https://web.whatsapp.com' }
      });
    } catch {
      return new Response('Upstream unavailable', { status: 502 });
    }
    if (upstreamResponse.status !== 101 || !upstreamResponse.webSocket) {
      return new Response('Upstream did not accept WebSocket', { status: 502 });
    }

    const upstream = upstreamResponse.webSocket;
    const [client, server] = Object.values(new WebSocketPair());
    server.accept({ allowHalfOpen: true });
    upstream.accept({ allowHalfOpen: true });
    couple(server, upstream);
    return new Response(null, { status: 101, webSocket: client });
  }
};
