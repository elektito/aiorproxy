#!/usr/bin/env python3

import asyncio
import aioredis
from aiohttp import web, ClientSession
from yarl import URL

async def handle(request, session, redis):
    # Lookup the backend on redis.
    key = '{}:{}'.format(request.url.host, request.url.port)
    value = await redis.get(key)
    if not value:
        raise web.HTTPNotFound
    backend_host, backend_port = value.decode().split(':')
    backend_port = int(backend_port)
    url = request.url.with_host(backend_host).with_port(backend_port)

    # Send an equivalent request to the backend.
    headers = request.headers.copy()
    headers['Host'] = '{}:{}'.format(backend_host, backend_port)
    data = request.content if request.has_body else None
    async with session.request(request.method, url,
                               allow_redirects=False,
                               data=data,
                               headers=headers) as resp:
        # Create a new response.
        out_resp = web.Response(status=resp.status)

        # Copy received headers into the new response.
        for k, v in resp.headers.items():
            out_resp.headers[k] = v

        # Fix 'Location' header on redirect.
        if int(resp.status / 100) == 3 and 'Location' in resp.headers:
            location = URL(resp.headers['Location'])
            if location.host:
                location = location.with_host(request.url.host)
                location = location.with_port(request.url.port)
                out_resp.headers['Location'] = str(location)

        # Send headers.
        await out_resp.prepare(request)

        # Stream response back to the client.
        while True:
            chunk = await resp.content.readany()
            if not chunk:
                break
            out_resp.write(chunk)
        out_resp.write_eof()

        return out_resp

loop = asyncio.get_event_loop()
redis = loop.run_until_complete(aioredis.create_redis(('localhost', 6379)))
session = ClientSession()
app = web.Application()
app.router.add_route(
    '*', '/{tail:.*}', lambda r: handle(r, session, redis))
