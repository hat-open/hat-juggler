"""Juggler client"""

import asyncio
import itertools
import logging
import typing
import ssl

import aiohttp

from hat import aio
from hat import json

from hat.juggler.transport import Transport


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

NotifyCb: typing.TypeAlias = aio.AsyncCallable[['Client', str, json.Data],
                                               None]
"""Notify callback"""


class JugglerError(Exception):
    """Juggler error"""

    def __init__(self, data: json.Data):
        self.__data = data

    @property
    def data(self) -> json.Data:
        """Error data"""
        return self.__data


async def connect(address: str,
                  notify_cb: NotifyCb | None = None,
                  *,
                  auth: aiohttp.BasicAuth | None = None,
                  ssl_ctx: ssl.SSLContext | None = None,
                  send_queue_size: int = 1024,
                  max_segment_size: int = 64 * 1024,
                  ping_delay: float = 30,
                  ping_timeout: float = 30
                  ) -> 'Client':
    """Connect to remote server

    `address` represents remote WebSocket URL formated as
    ``<schema>://<host>:<port>/<path>`` where ``<schema>`` is ``ws`` or
    ``wss``.

    """
    client = Client()
    client._notify_cb = notify_cb
    client._loop = asyncio.get_running_loop()
    client._async_group = aio.Group()
    client._state = json.Storage()
    client._res_futures = {}
    client._next_req_ids = itertools.count(1)
    client._session = aiohttp.ClientSession()

    try:
        ws = await client._session.ws_connect(address,
                                              auth=auth,
                                              ssl=ssl_ctx or False,
                                              max_msg_size=0)

    except BaseException:
        await aio.uncancellable(client._session.close())
        raise

    client._transport = Transport(ws=ws,
                                  msg_cb=client._on_msg,
                                  send_queue_size=send_queue_size,
                                  max_segment_size=max_segment_size,
                                  ping_delay=ping_delay,
                                  ping_timeout=ping_timeout)

    client.async_group.spawn(aio.call_on_cancel, client._on_close)
    client.async_group.spawn(aio.call_on_done,
                             client._transport.wait_closing(), client.close)

    return client


class Client(aio.Resource):
    """Client

    For creating new client see `connect` coroutine.

    """

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    @property
    def state(self) -> json.Storage:
        """Remote server state"""
        return self._state

    async def send(self,
                   name: str,
                   data: json.Data
                   ) -> json.Data:
        """Send request and wait for response

        Args:
            name: request name
            data: request payload

        Raises:
            JugglerError
            ConnectionError

        """
        if not self.is_open:
            raise ConnectionError()

        req_id = next(self._next_req_ids)
        res_future = self._loop.create_future()
        self._res_futures[req_id] = res_future

        try:
            await self._transport.send({'type': 'request',
                                        'id': req_id,
                                        'name': name,
                                        'data': data})
            return await res_future

        finally:
            self._res_futures.pop(req_id)

    async def _on_close(self):
        for f in self._res_futures.values():
            if not f.done():
                f.set_exception(ConnectionError())

        await self._transport.async_close()
        await self._session.close()

    async def _on_msg(self, msg):
        if msg['type'] == 'response':
            res_future = self._res_futures.get(msg['id'])
            if not res_future or res_future.done():
                return

            if msg['success']:
                res_future.set_result(msg['data'])

            else:
                res_future.set_exception(JugglerError(msg['data']))

        elif msg['type'] == 'state':
            data = json.patch(self._state.data, msg['diff'])
            self._state.set([], data)

        elif msg['type'] == 'notify':
            if not self._notify_cb:
                return

            await aio.call(self._notify_cb, self, msg['name'],
                           msg['data'])

        else:
            raise Exception("invalid message type")
