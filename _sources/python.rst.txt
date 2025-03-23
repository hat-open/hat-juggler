`hat.juggler` - Python juggler library
======================================

This library provides Python implementation of
:ref:`Juggler communication protocol <juggler>`.


Client
------

`hat.juggler.connect` coroutine creates client::

    NotifyCb = aio.AsyncCallable[['Client', str, json.Data], None]

    async def connect(address: str,
                      notify_cb: typing.Optional[NotifyCb] = None
                      ) -> 'Client':

    class Client(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def state(self) -> json.Storage: ...

        async def send(self,
                       name: str,
                       data: json.Data
                       ) -> json.Data: ...


Server
------

`hat.juggler.listen` coroutine creates server listening for incomming
juggler connections::

    ConnectionCb = aio.AsyncCallable[['Connection'], None]

    RequestCb = aio.AsyncCallable[['Connection', str, json.Data], json.Data]

    async def listen(host: str,
                     port: int,
                     connection_cb: ConnectionCb | None = None,
                     request_cb: RequestCb | None = None,
                     *,
                     ws_path: str = '/ws',
                     static_dir: pathlib.PurePath | None = None,
                     index_path: str | None = '/index.html',
                     htpasswd_file: pathlib.PurePath | None = None,
                     ssl_ctx: ssl.SSLContext | None = None,
                     autoflush_delay: float | None = 0.2,
                     shutdown_timeout: float = 0.1,
                     state: json.Storage | None = None,
                     parallel_requests: bool = False,
                     additional_routes: Iterable[aiohttp.web.RouteDef] = []
                     ) -> 'Server':

    class Server(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

    class Connection(aio.Resource):

        @property
        def async_group(self) -> aio.Group: ...

        @property
        def remote(self) -> str: ...

        @property
        def state(self) -> json.Storage: ...

        async def flush(self): ...

        async def notify(self,
                         name: str,
                         data: json.Data): ...


Example
-------

::

    from hat import aio
    from hat import juggler
    from hat import util

    port = util.get_unused_tcp_port()
    host = '127.0.0.1'

    conns = aio.Queue()
    server = await juggler.listen(host, port, conns.put_nowait,
                                  autoflush_delay=0)

    client = await juggler.connect(f'ws://{host}:{port}/ws')
    conn = await conns.get()

    data = aio.Queue()
    client.state.register_change_cb(data.put_nowait)

    conn.state.set([], 123)
    data = await data.get()
    assert data == 123

    await server.async_close()
    await conn.wait_closed()
    await client.wait_closed()


API
---

API reference is available as part of generated documentation:

    * `Python hat.juggler module <py_api/hat/juggler.html>`_
