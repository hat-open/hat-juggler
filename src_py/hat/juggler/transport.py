import asyncio
import collections
import contextlib
import logging
import typing

import aiohttp.web

from hat import aio
from hat import json


mlog: logging.Logger = logging.getLogger(__name__)
"""Module logger"""

WebSocket: typing.TypeAlias = (aiohttp.web.WebSocketResponse |
                               aiohttp.ClientWebSocketResponse)
"""WebSocket connection"""

Msg: typing.TypeAlias = json.Data
"""Message"""

MsgCb: typing.TypeAlias = aio.AsyncCallable[[Msg], None]
"""Message callback"""


class Transport(aio.Resource):
    """Transport connection"""

    def __init__(self,
                 ws: WebSocket,
                 msg_cb: MsgCb,
                 send_queue_size: int,
                 max_segment_size: int,
                 ping_delay: float,
                 ping_timeout: float):
        self._ws = ws
        self._msg_cb = msg_cb
        self._max_segment_size = max_segment_size
        self._ping_delay = ping_delay
        self._ping_timeout = ping_timeout
        self._async_group = aio.Group()
        self._send_queue = aio.Queue(send_queue_size)
        self._receive_event = asyncio.Event()

        self.async_group.spawn(self._receive_loop)
        self.async_group.spawn(self._send_loop)
        self.async_group.spawn(self._ping_loop)

    @property
    def async_group(self) -> aio.Group:
        """Async group"""
        return self._async_group

    async def send(self, msg: Msg):
        """Send message"""
        try:
            await self._send_queue.put(msg)

        except aio.QueueClosedError:
            raise ConnectionError()

    async def _receive_loop(self):
        try:
            data_queue = collections.deque()

            while self.is_open:
                msg_ws = await self._ws.receive()
                if self._ws.closed or msg_ws.type == aiohttp.WSMsgType.CLOSING:
                    break
                if msg_ws.type != aiohttp.WSMsgType.TEXT:
                    raise Exception("unsupported ws message type")

                self._receive_event.set()

                data_type = msg_ws.data[0]
                payload = msg_ws.data[1:]

                if data_type == '0':
                    data_queue.append(payload)

                    data_str = ''.join(data_queue)
                    data_queue = collections.deque()
                    data = json.decode(data_str)

                    await aio.call(self._msg_cb, data)

                elif data_type == '1':
                    data_queue.append(payload)

                elif data_type == '2':
                    await self._ws.send_str('3' + payload)

                elif data_type == '3':
                    pass

                else:
                    raise Exception('invalid message type')

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error("receive loop error: %s", e, exc_info=e)

        finally:
            self.close()
            await aio.uncancellable(self._ws.close())

    async def _send_loop(self):
        try:
            while True:
                msg = await self._send_queue.get()

                msg_str = json.encode(msg)
                pos = 0
                more_follows = True

                while more_follows:
                    payload = msg_str[pos:pos + self._max_segment_size]
                    pos += len(payload)

                    more_follows = pos < len(msg_str)
                    data_type = '1' if more_follows else '0'

                    await self._ws.send_str(data_type + payload)

        except ConnectionError:
            pass

        except Exception as e:
            mlog.error("send loop error: %s", e, exc_info=e)

        finally:
            self.close()
            self._send_queue.close()

    async def _ping_loop(self):
        try:
            while True:
                self._receive_event.clear()

                with contextlib.suppress(asyncio.TimeoutError):
                    await aio.wait_for(self._receive_event.wait(),
                                       self._ping_delay)
                    continue

                await self._ws.send_str('2')

                await aio.wait_for(self._receive_event.wait(),
                                   self._ping_timeout)

        except ConnectionError:
            pass

        except asyncio.TimeoutError:
            mlog.error("ping timeout")

        except Exception as e:
            mlog.error("ping loop error: %s", e, exc_info=e)

        finally:
            self.close()
