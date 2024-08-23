import asyncio
import contextlib
import logging.config

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

    async def cleanup():
        mlog.info('closing server')
        await srv.async_close()
        mlog.info('server closed')

    mlog.info('creating server')
    srv = await juggler.listen('127.0.0.1', 1234)
    mlog.info('server created')

    try:
        await srv.wait_closing()

    finally:
        await aio.uncancellable(cleanup())


if __name__ == '__main__':
    main()
