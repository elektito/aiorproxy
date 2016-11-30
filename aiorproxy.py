#!/usr/bin/env python3

import asyncio
import aioredis
from aiohttp import web, ClientSession

async def handle(request, session, redis):
    key = '{}:{}'.format(request.url.host, request.url.port)
    value = await redis.get(key)
    if not value:
        raise web.HTTPNotFound
    backend_host, backend_port = value.decode().split(':')
    backend_port = int(backend_port)
    url = request.url.with_host(backend_host).with_port(backend_port)
    headers = request.headers.copy()
    headers['Host'] = '{}:{}'.format(backend_host, backend_port)
    data = request.content if request.has_body else None
    async with session.request(request.method, url,
                               data=data,
                               headers=headers) as resp:
        out_resp = web.Response(status=resp.status)
        for k, v in resp.headers.items():
            out_resp.headers[k] = v
        await out_resp.prepare(request)
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
