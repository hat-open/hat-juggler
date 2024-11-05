import asyncio
import pathlib

import aiohttp.hdrs
import aiohttp.web

from hat import aio


@aiohttp.web.middleware
class BasicAuthMiddleware:

    def __init__(self, htpasswd_file: pathlib.PurePath):
        self._user_password_hashes = {}
        self._user_passwords = {}

        with open(htpasswd_file, 'r', encoding='utf-8') as f:
            while True:
                line = f.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                user, password_hash = line.split(':', 1)

                if not password_hash.startswith('$apr1$'):
                    raise Exception('unsupported password encoding')

                self._user_password_hashes[user] = password_hash

    async def __call__(self, request, handler):
        try:
            auth_header = request.headers.get(aiohttp.hdrs.AUTHORIZATION)
            auth = aiohttp.BasicAuth.decode(auth_header=auth_header)

            if auth.login in self._user_passwords:
                if self._user_passwords[auth.login] != auth.password:
                    raise Exception('invalid password')

            elif auth.login in self._user_password_hashes:
                await _verify_password(auth.password,
                                       self._user_password_hashes[auth.login])
                self._user_passwords[auth.login] = auth.password

            else:
                raise Exception('invalid user')

        except Exception:
            raise aiohttp.web.HTTPUnauthorized(
                reason='Unauthorized',
                headers={aiohttp.hdrs.WWW_AUTHENTICATE: 'Basic realm=""'})

        return await handler(request)


async def _verify_password(password, password_hash):
    if not password_hash.startswith('$apr1$'):
        raise Exception('invalid hash')

    salt = password_hash[6:].split('$', 1)[0]

    p = await asyncio.create_subprocess_exec(
        'openssl', 'passwd', '-stdin', '-apr1', '-salt', salt,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    try:
        stdout_data, stderr_data = await p.communicate(password.encode())

    finally:
        await aio.uncancellable(_close_process(p))

    if p.returncode:
        raise Exception(str(stderr_data, encoding='utf-8', errors='ignore'))

    result = str(stdout_data, encoding='utf-8').strip()
    if result != password_hash:
        raise Exception('invalid password')


async def _close_process(p,
                         sigterm_timeout=1,
                         sigkill_timeout=1):
    if p.returncode is not None:
        return

    p.terminate()

    await aio.wait_for(p.wait(), sigterm_timeout)

    if p.returncode is not None:
        return

    p.kill()

    if p.returncode is not None:
        return

    await aio.wait_for(p.wait(), sigkill_timeout)
