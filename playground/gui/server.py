from pathlib import Path
import asyncio
import contextlib
import logging.config
import sys

from hat import aio

from hat import juggler


mlog = logging.getLogger('server')


def main():
    logging.config.dictConfig({
        'version': 1,
        'formatters': {
            'console_formatter': {
                'format': "[%(asctime)s %(levelname)s %(name)s] %(message)s"}},
        'handlers': {
            'console_handler': {
                'class': 'logging.StreamHandler',
                'formatter': 'console_formatter',
                'level': 'DEBUG'}},
        'root': {
            'level': 'INFO',
            'handlers': ['console_handler']},
        'disable_existing_loggers': False})

    with contextlib.suppress(asyncio.CancelledError):
        aio.run_asyncio(async_main())


async def async_main():
    root_dir = Path(sys.argv[1]).resolve()
    index_path = Path(sys.argv[2]).resolve()

    async def cleanup():
        mlog.info('closing server')
        await srv.async_close()
        mlog.info('server closed')

    mlog.info('creating server')
    srv = await juggler.listen(
        '127.0.0.1', 1234,
        request_cb=on_request,
        static_dir=root_dir,
        index_path=str(index_path.relative_to(root_dir)))
    mlog.info('server created')

    try:
        await srv.wait_closing()

    finally:
        await aio.uncancellable(cleanup())


async def on_request(conn, name, data):
    print('>>', name, data)


if __name__ == '__main__':
    main()
