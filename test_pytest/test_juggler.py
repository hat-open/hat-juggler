import asyncio

import pytest

from hat import aio
from hat import juggler
from hat import util


host = '127.0.0.1'


@pytest.fixture
def port():
    return util.get_unused_udp_port()


@pytest.fixture
def address(port):
    return f'ws://127.0.0.1:{port}/ws'


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_connect_listen(port, address, client_count):
    conn_queue = aio.Queue()
    conns = []
    clients = []

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)

    for i in range(client_count):
        client = await juggler.connect(address)
        clients.append(client)

        conn = await conn_queue.get()
        conns.append(conn)

    assert server.is_open

    for client, conn in zip(clients, conns):
        assert client.is_open
        assert conn.is_open

    for client, conn in zip(clients, conns):
        await client.async_close()
        await conn.async_close()

    await server.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_close_client(port, address, client_count):
    conn_queue = aio.Queue()
    conns = []
    clients = []

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)

    for i in range(client_count):
        client = await juggler.connect(address)
        clients.append(client)

        conn = await conn_queue.get()
        conns.append(conn)

    for client, conn in zip(clients, conns):
        await client.async_close()
        await conn.wait_closed()

    await server.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_close_connection(port, address, client_count):
    conn_queue = aio.Queue()
    conns = []
    clients = []

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)

    for i in range(client_count):
        client = await juggler.connect(address)
        clients.append(client)

        conn = await conn_queue.get()
        conns.append(conn)

    for client, conn in zip(clients, conns):
        await conn.async_close()
        await client.wait_closed()

    await server.async_close()


@pytest.mark.parametrize("client_count", [1, 2, 5])
async def test_close_server(port, address, client_count):
    conn_queue = aio.Queue()
    conns = []
    clients = []

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)

    for i in range(client_count):
        client = await juggler.connect(address)
        clients.append(client)

        conn = await conn_queue.get()
        conns.append(conn)

    await server.async_close()

    for client, conn in zip(clients, conns):
        await conn.wait_closed()
        await client.wait_closed()


@pytest.mark.parametrize("name", ['name1', 'name2'])
@pytest.mark.parametrize("data", [None, 42, '42', [], {'a': [True, {}]}])
async def test_notify(port, address, name, data):
    conn_queue = aio.Queue()
    notify_queue = aio.Queue()

    def on_notify(c, name, data):
        assert c is client
        notify_queue.put_nowait((name, data))

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)
    client = await juggler.connect(address=address,
                                   notify_cb=on_notify)
    conn = await conn_queue.get()

    await conn.notify(name, data)

    n, d = await notify_queue.get()
    assert n == name
    assert d == data

    await conn.async_close()
    await client.async_close()
    await server.async_close()


async def test_big_notify(port, address):
    conn_queue = aio.Queue()
    notify_queue = aio.Queue()

    def on_notify(client, name, data):
        notify_queue.put_nowait((name, data))

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)
    client = await juggler.connect(address=address,
                                   notify_cb=on_notify)
    conn = await conn_queue.get()

    data = '1' * 4194304 * 2
    await conn.notify('big', data)

    n, d = await notify_queue.get()
    assert n == 'big'
    assert d == data

    await conn.async_close()
    await client.async_close()
    await server.async_close()


@pytest.mark.parametrize("name", ['name1', 'name2'])
@pytest.mark.parametrize("data", [None, 42, '42', [], {'a': [True, {}]}])
async def test_request_response(port, address, name, data):
    conn_queue = aio.Queue()
    req_queue = aio.Queue()

    async def on_request(c, name, data):
        assert c is conn
        future = asyncio.Future()
        req_queue.put_nowait((name, data, future))
        return await future

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait,
                                  request_cb=on_request)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    res_future = asyncio.create_task(client.send(name, data))

    n, d, f = await req_queue.get()
    assert n == name
    assert d == data
    assert not res_future.done()

    f.set_result(['response', data])
    res = await res_future

    assert res == ['response', data]

    await conn.async_close()
    await client.async_close()
    await server.async_close()


async def test_request_response_exception(port, address):
    conn_queue = aio.Queue()

    async def on_request(c, name, data):
        assert c is conn
        assert name == 'name'
        assert data == 42
        raise Exception('error')

    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait,
                                  request_cb=on_request)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    try:
        await client.send('name', 42)
        assert False

    except juggler.JugglerError as e:
        assert e.data == 'error'

    await conn.async_close()
    await client.async_close()
    await server.async_close()


async def test_request_response_not_implemented(port, address):
    conn_queue = aio.Queue()
    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    with pytest.raises(juggler.JugglerError):
        await client.send('name', 42)

    await conn.async_close()
    await client.async_close()
    await server.async_close()


@pytest.mark.parametrize("change_count", [1, 10, 100, 10000])
async def test_state(port, address, change_count):
    conn_queue = aio.Queue()
    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait,
                                  autoflush_delay=0.001)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    assert conn.state.data is None
    assert client.state.data is None

    data_queue = aio.Queue()
    with client.state.register_change_cb(data_queue.put_nowait):
        for i in range(change_count):
            conn.state.set([], i)
            await asyncio.sleep(0)

        while True:
            data = await data_queue.get()
            assert data < change_count
            if data == change_count - 1:
                break

        assert data_queue.empty()

    await conn.async_close()
    await client.async_close()
    await server.async_close()


@pytest.mark.parametrize("change_count", [1, 10, 100, 10000])
async def test_state_flush(port, address, change_count):
    conn_queue = aio.Queue()
    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait,
                                  autoflush_delay=None)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    assert conn.state.data is None
    assert client.state.data is None

    data_queue = aio.Queue()
    with client.state.register_change_cb(data_queue.put_nowait):
        for i in range(change_count):
            conn.state.set([], i)
            await asyncio.sleep(0)

        assert data_queue.empty()

        await conn.flush()
        data = await data_queue.get()

        assert data == change_count - 1
        assert data_queue.empty()

    await conn.async_close()
    await client.async_close()
    await server.async_close()


@pytest.mark.parametrize("change_count", [1, 10, 100])
async def test_state_sync(port, address, change_count):
    conn_queue = aio.Queue()
    server = await juggler.listen(host=host,
                                  port=port,
                                  connection_cb=conn_queue.put_nowait,
                                  autoflush_delay=0)
    client = await juggler.connect(address)
    conn = await conn_queue.get()

    assert conn.state.data is None
    assert client.state.data is None

    data_queue = aio.Queue()
    with client.state.register_change_cb(data_queue.put_nowait):
        for i in range(change_count):
            conn.state.set([], i)
            await asyncio.sleep(0)

        for i in range(change_count):
            data = await data_queue.get()
            assert data == i

        assert data_queue.empty()

    await conn.async_close()
    await client.async_close()
    await server.async_close()


async def test_example_docs():

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
