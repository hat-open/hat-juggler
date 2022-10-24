"""Juggler server"""

import asyncio
import logging
import pathlib
import ssl
import typing

import aiohttp.web

from hat import aio
from hat import json
from hat import util


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

ConnectionCb = aio.AsyncCallable[['Connection'], None]
"""Connection callback"""

RequestCb = aio.AsyncCallable[['Connection', str, json.Data], json.Data]
"""Request callback"""


async def listen(host: str,
                 port: int,
                 connection_cb: ConnectionCb,
                 request_cb: typing.Optional[RequestCb] = None, *,
                 ws_path: str = '/ws',
                 static_dir: typing.Optional[pathlib.PurePath] = None,
                 index_path: typing.Optional[str] = '/index.html',
                 pem_file: typing.Optional[pathlib.PurePath] = None,
                 autoflush_delay: typing.Optional[float] = 0.2,
                 shutdown_timeout: float = 0.1
                 ) -> 'Server':
    """Create listening server

    Each time server receives new incoming juggler connection, `connection_cb`
    is called with newly created connection.

    For each connection, when server receives `request` message, `request_cb`
    is called with associated connection, request name and request data.
    If `request_cb` returns value, successful `response` message is sent
    with resulting value as data. If `request_cb` raises exception,
    unsuccessful `response` message is sent with raised exception as data.
    If `request_cb` is ``None``, each `request` message causes sending
    of unsuccessful `response` message.

    If `static_dir` is set, server serves static files is addition to providing
    juggler communication.

    If `index_path` is set, request for url path ``/`` are redirected to
    `index_path`.

    If `pem_file` is set, server provides `https/wss` communication instead
    of `http/ws` communication.

    Argument `autoflush_delay` is associated with all connections associated
    with this server. `autoflush_delay` defines maximum time delay for
    automatic synchronization of `state` changes. If `autoflush_delay` is set
    to ``None``, automatic synchronization is disabled and user is responsible
    for calling :meth:`Connection.flush`. If `autoflush_delay` is set to ``0``,
    synchronization of `state` is performed on each change of `state` data.

    `shutdown_timeout` defines maximum time duration server will wait for
    regular connection close procedures during server shutdown. All connections
    that are not closed during this period are forcefully closed.

    Args:
        host: listening hostname
        port: listening TCP port
        connection_cb: connection callback
        request_cb: request callback
        ws_path: WebSocket url path segment
        static_dir: static files directory path
        index_path: index path
        pem_file: PEM file path
        autoflush_delay: autoflush delay
        shutdown_timeout: shutdown timeout

    """
    server = Server()
    server._connection_cb = connection_cb
    server._request_cb = request_cb
    server._autoflush_delay = autoflush_delay
    server._async_group = aio.Group()

    routes = []

    if index_path:

        async def root_handler(request):
            raise aiohttp.web.HTTPFound(index_path)

        routes.append(aiohttp.web.get('/', root_handler))

    routes.append(aiohttp.web.get(ws_path, server._ws_handler))

    if static_dir:
        routes.append(aiohttp.web.static('/', static_dir))

    app = aiohttp.web.Application()
    app.add_routes(routes)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    server.async_group.spawn(aio.call_on_cancel, runner.cleanup)

    try:
        ssl_ctx = _create_ssl_context(pem_file) if pem_file else None
        site = aiohttp.web.TCPSite(runner=runner,
                                   host=host,
                                   port=port,
                                   shutdown_timeout=shutdown_timeout,
                                   ssl_context=ssl_ctx,
                                   reuse_address=True)
        await site.start()

    except BaseException:
        await aio.uncancellable(server.async_close())
        raise

    return server


class Server(aio.Resource):
    """Server

    For creating new server see `listen` coroutine.

    When server is closed, all incoming connections are also closed.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def _ws_handler(self, request):
        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)

        conn = Connection()
        conn._ws = ws
        conn._async_group = self.async_group.create_subgroup()
        conn._request_cb = self._request_cb
        conn._autoflush_delay = self._autoflush_delay
        conn._state = json.Storage()
        conn._flush_queue = aio.Queue()

        conn.async_group.spawn(conn._receive_loop)
        conn.async_group.spawn(conn._sync_loop)
        conn.async_group.spawn(aio.call, self._connection_cb, conn)

        await conn.wait_closed()

        return ws


class Connection(aio.Resource):
    """Connection

    For creating new connection see `listen` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def state(self) -> json.Storage:
        """Server state"""
        return self._state

    async def flush(self):
        """Force synchronization of state data

        Raises:
            ConnectionError

        """
        try:
            flush_future = asyncio.Future()
            self._flush_queue.put_nowait(flush_future)
            await flush_future

        except aio.QueueClosedError:
            raise ConnectionError()

    async def notify(self,
                     name: str,
                     data: json.Data):
        """Send notification

        Raises:
            ConnectionError

        """
        if not self.is_open:
            raise ConnectionError()

        await self._ws.send_json({'type': 'notify',
                                  'name': name,
                                  'data': data})

    async def _receive_loop(self):
        try:
            while True:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception("unsupported ws message type")

                msg = json.decode(msg_ws.data)

                if msg['type'] != 'request':
                    raise Exception("invalid message type")

                res = {'type': 'response',
                       'id': msg['id']}

                if msg['name']:
                    try:
                        if not self._request_cb:
                            raise Exception('request handler not implemented')

                        res['data'] = await aio.call(self._request_cb, self,
                                                     msg['name'], msg['data'])
                        res['success'] = True

                    except Exception as e:
                        res['data'] = str(e)
                        res['success'] = False

                else:
                    res['data'] = msg['data']
                    res['success'] = True

                await self._ws.send_json(res)

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error("receive loop error: %s", e, exc_info=e)

        finally:
            self.close()
            await aio.uncancellable(self._ws.close())

    async def _sync_loop(self):
        flush_future = None
        data = None
        synced_data = None
        data_queue = aio.Queue()

        try:
            with self._state.register_change_cb(data_queue.put_nowait):
                data_queue.put_nowait(self._state.data)

                if not self.is_open:
                    return

                get_data_future = self.async_group.spawn(data_queue.get)
                get_flush_future = self.async_group.spawn(
                    self._flush_queue.get)

                while True:
                    await asyncio.wait([get_data_future, get_flush_future],
                                       return_when=asyncio.FIRST_COMPLETED)

                    if get_flush_future.done():
                        flush_future = get_flush_future.result()
                        get_flush_future = self.async_group.spawn(
                            self._flush_queue.get)

                    else:
                        await asyncio.wait([get_flush_future],
                                           timeout=self._autoflush_delay)

                        if get_flush_future.done():
                            flush_future = get_flush_future.result()
                            get_flush_future = self.async_group.spawn(
                                self._flush_queue.get)

                        else:
                            flush_future = None

                    if get_data_future.done():
                        data = get_data_future.result()
                        get_data_future = self.async_group.spawn(
                            data_queue.get)

                    if self._autoflush_delay != 0:
                        if not data_queue.empty():
                            data = data_queue.get_nowait_until_empty()

                    if synced_data is not data:
                        diff = json.diff(synced_data, data)
                        synced_data = data

                        if diff:
                            await self._ws.send_json({'type': 'state',
                                                      'diff': diff})

                    if flush_future and not flush_future.done():
                        flush_future.set_result(True)

        except Exception as e:
            mlog.error("sync loop error: %s", e, exc_info=e)

        finally:
            self.close()

            self._flush_queue.close()
            while True:
                if flush_future and not flush_future.done():
                    flush_future.set_exception(ConnectionError())

                if self._flush_queue.empty():
                    break

                flush_future = self._flush_queue.get_nowait()


def _create_ssl_context(pem_file):
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    ssl_ctx.verify_mode = ssl.VerifyMode.CERT_NONE
    if pem_file:
        ssl_ctx.load_cert_chain(str(pem_file))
    return ssl_ctx


# HACK
util.register_type_alias('ConnectionCb')
util.register_type_alias('RequestCb')
