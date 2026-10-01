"""One local server whose lifetime follows the last GUI browser tab."""
import asyncio
import json
import socket
import urllib.request
import webbrowser
import uuid

import uvicorn

from .app import create_app
from .browser_lifetime import BrowserLifetime

URL = 'http://127.0.0.1:8002'


def browser_url():
    # Also bypass pages cached before the server started sending no-store.
    return URL + '/?launch=' + uuid.uuid4().hex


def open_existing():
    """Only reuse a server that explicitly advertises browser-owned lifetime."""
    try:
        with urllib.request.urlopen(URL + '/api/status', timeout=3) as response:
            status = json.load(response)
        if status.get('browser_managed') is True:
            webbrowser.open(browser_url())
            return True
    except (OSError, ValueError):
        pass
    print('Port 8002 is already in use by an older server or another application.')
    print('Stop that server once (Ctrl+C in its terminal), then launch again.')
    return False


async def serve(sock):
    lifetime = BrowserLifetime(lambda: setattr(server, 'should_exit', True))
    app = create_app(browser_lifetime=lifetime)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=8002,
                                         timeout_graceful_shutdown=2))

    async def open_when_ready():
        while not server.started and not server.should_exit:
            await asyncio.sleep(.05)
        if server.started and not server.should_exit:
            await asyncio.to_thread(webbrowser.open, browser_url())

    browser_task = asyncio.create_task(open_when_ready())
    try:
        await server.serve(sockets=[sock])
    finally:
        browser_task.cancel()
        await asyncio.gather(browser_task, return_exceptions=True)


def main():
    # Bind BEFORE Engine startup: a duplicate launch must not touch runtime
    # records or mark another live server's operations interrupted.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(('127.0.0.1', 8002))
        except OSError:
            return 0 if open_existing() else 1
        print('Close the last GUI tab/window to stop operations and shut down the server.')
        print('Refresh is allowed a 3-second reconnect grace period.')
        asyncio.run(serve(sock))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
