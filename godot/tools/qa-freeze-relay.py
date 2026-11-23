#!/usr/bin/env python3
"""QA only: a TCP relay in front of an HTTPS (CONNECT) proxy that can turn the connections it
already carries into dead ones, the way a phone's link dies after a network change or a NAT
timeout: bytes are swallowed in both directions and the sockets are never closed. New
connections are relayed normally. SIGUSR1 freezes every connection open at that moment.
Logs one line per connection event (no payload, no headers) to stderr.

usage: qa-freeze-relay.py LISTEN_PORT UPSTREAM_HOST UPSTREAM_PORT
"""
import asyncio, signal, sys, time

LISTEN, UP_HOST, UP_PORT = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
T0 = time.monotonic()
links = {}
next_id = 0

def log(*parts):
    print('%8.3f' % (time.monotonic() - T0), *parts, file=sys.stderr, flush=True)

async def pump(link, reader, writer, direction):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            if link['frozen']:
                link['swallowed'] += len(data)
                continue
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    if not link['frozen']:
        try:
            writer.close()
        except Exception:
            pass

async def handle(client_r, client_w):
    global next_id
    next_id += 1
    link = {'id': next_id, 'frozen': False, 'swallowed': 0, 'opened': time.monotonic()}
    links[link['id']] = link
    log('open', link['id'])
    try:
        up_r, up_w = await asyncio.open_connection(UP_HOST, UP_PORT)
    except OSError as error:
        log('upstream-failed', link['id'], error)
        client_w.close()
        return
    await asyncio.gather(pump(link, client_r, up_w, 'up'), pump(link, up_r, client_w, 'down'))
    links.pop(link['id'], None)
    log('close', link['id'], 'frozen' if link['frozen'] else '', 'swallowed=%d' % link['swallowed'],
        'life=%.1fs' % (time.monotonic() - link['opened']))

def freeze():
    ids = [k for k, v in links.items() if not v['frozen']]
    for k in ids:
        links[k]['frozen'] = True
    log('freeze', ids)

async def main():
    server = await asyncio.start_server(handle, '127.0.0.1', LISTEN)
    asyncio.get_running_loop().add_signal_handler(signal.SIGUSR1, freeze)
    log('listening', LISTEN)
    async with server:
        await server.serve_forever()

asyncio.run(main())
