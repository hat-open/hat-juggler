"""Juggler client"""

import asyncio
import itertools
import logging
import typing

import aiohttp

from hat import aio
from hat import json


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
                  notify_cb: NotifyCb | None = None
                  ) -> 'Client':
    """Connect to remote server

    `address` represents remote WebSocket URL formated as
    ``<schema>://<host>:<port>/<path>`` where ``<schema>`` is ``ws`` or
    ``wss``.

    """
    client = Client()
    client._notify_cb = notify_cb
    client._async_group = aio.Group()
    client._state = json.Storage()
    client._res_futures = {}
    client._next_req_ids = itertools.count(1)
    client._session = aiohttp.ClientSession()

    try:
        client._ws = await client._session.ws_connect(address, max_msg_size=0)

    except BaseException:
        await aio.uncancellable(client._session.close())
        raise

    client.async_group.spawn(client._receive_loop)

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
        res_future = asyncio.Future()
        self._res_futures[req_id] = res_future

        try:
            await self._ws.send_json({'type': 'request',
                                      'id': req_id,
                                      'name': name,
                                      'data': data})
            return await res_future

        finally:
            self._res_futures.pop(req_id)

    async def _receive_loop(self):
        try:
            while True:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception("unsupported ws message type")

                msg = json.decode(msg_ws.data)

                if msg['type'] == 'response':
                    res_future = self._res_futures.get(msg['id'])
                    if not res_future or res_future.done():
                        continue

                    if msg['success']:
                        res_future.set_result(msg['data'])

                    else:
                        res_future.set_exception(JugglerError(msg['data']))

                elif msg['type'] == 'state':
                    data = json.patch(self._state.data, msg['diff'])
                    self._state.set([], data)

                elif msg['type'] == 'notify':
                    if not self._notify_cb:
                        continue

                    await aio.call(self._notify_cb, self, msg['name'],
                                   msg['data'])

                else:
                    raise Exception("invalid message type")

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error("receive loop error: %s", e, exc_info=e)

        finally:
            self.close()

            for f in self._res_futures.values():
                if not f.done():
                    f.set_exception(ConnectionError())

            await aio.uncancellable(self._close_ws())

    async def _close_ws(self):
        await self._ws.close()
        await self._session.close()
