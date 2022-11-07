import traceback
import json
from typing import Dict, Any, Callable, Awaitable, Optional, Tuple

from ._app import InteractionApp


class InteractionASGIApp:
    def __init__(self, app: InteractionApp, *,  method: str = 'POST', path: str = '/') -> None:
        self._app = app

        self.method = method
        self.path = path

    async def _lifespan(
        self,
        receive: Callable[[], Awaitable[Dict[str, Any]]],
        send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        event = await receive()
        if event['type'] == 'lifespan.startup':
            try:
                await self._app.__aenter__()
            except Exception as exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__)
                await send({'type': 'lifespan.startup.failed'})
            else:
                await send({'type': 'lifespan.startup.complete'})

        elif event['type'] == 'lifespan.shutdown':
            try:
                await self._app.__aexit__(None, None, None)
            except Exception as exc:
                traceback.print_exception(type(exc), exc, exc.__traceback__)
                await send({'type': 'lifespan.shutdown.failed'})
            else:
                await send({'type': 'lifespan.shutdown.complete'})

    async def _verify_request_target(
        self,
        scope: Dict[str, Any],
        send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> bool:
        """Verify that the request was made to the correct endpoint.

        This method will respond to the request with an appropriate response
        if the request was made to the wrong endpoint.

        Returns:
            A boolean indicating whether the request was responded to. You
            should return if this is `True`.
        """
        if scope['type'] != 'http':
            await send({
                'type': 'http.response.start', 'status': 501,
                'headers': [(b'content-type', b'text/plain')]
            })
            await send({'type': 'http.response.body', 'body': b'Not Implemented'})
            return True

        if scope['path'] != self.path:
            await send({
                'type': 'http.response.start', 'status': 404,
                'headers': [(b'content-type', b'text/plain')]
            })
            await send({'type': 'http.response.body', 'body': b'Not Found'})
            return True

        elif scope['method'] != 'POST':
            await send({
                'type': 'http.response.start', 'status': 405,
                'headers': [(b'content-type', b'text/plain')]
            })
            await send({'type': 'http.response.body', 'body': b'Method Not Allowed'})
            return True

        return False

    async def _authenticate_request(
            self,
            scope: Dict[str, Any],
            receive: Callable[[], Awaitable[Dict[str, Any]]],
    ) -> Tuple[bool, Optional[bytes]]:
        signature: Optional[bytes] = None
        timestamp: Optional[bytes] = None

        for header, value in scope['headers']:
            if header == b'content-type' and value != b'application/json':
                # We can only handle application/json requests
                return False, None

            if header == b'x-signature-timestamp':
                timestamp = value
            elif header == b'x-signature-ed25519':
                signature = value

        if signature is None or timestamp is None:
            return False, None

        body = bytearray()
        # Initialize a fake request to make the while loop work
        request: Dict[str, Any] = {'more_body': True}
        while request['more_body']:
            request = await receive()
            body.extend(request['body'])

        if not self._app.authenticate_request(signature.decode('utf-8'), timestamp, body):
            return False, body

        return True, body

    def _create_response(
            self,
            scope: Dict[str, Any],
            receive: Callable[[], Awaitable[Dict[str, Any]]],
            send: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> Callable[[Dict[str, Any], List[Union[IO[bytes], bytes]]], Awaitable[object]]:
        async def respond_asgi(data: Dict[str, Any], files: List[Union[IO[bytes], bytes]]) -> None:
            if not files:
                await send({
                    'type': 'http.response.start', 'status': 200,
                    'headers': [(b'content-type', b'application/json')]
                })
                await send({
                    'type': 'http.response.body',
                    'body': json.dumps(data).encode('utf-8')
                })
                return

        return respond_asgi

    async def __call__(
            self,
            scope: Dict[str, Any],
            receive: Callable[[], Awaitable[Dict[str, Any]]],
            send: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        if scope['type'] == 'lifespan':
            return await self._lifespan(receive, send)

        if await self._verify_request_target(scope, send):
            # A response was sent and we should not process this further
            return

        verified, body = await self._authenticate_request(scope, receive)

        # The latter is for static type checkers, even though there is no case
        # were verified is True and body is None
        if not verified or body is None:
            await send({
                'type': 'http.response.start', 'status': 401,
                'headers': [(b'content-type', b'text/plain')]
            })
            await send({'type': 'http.response.body', 'body': b'Unauthorized'})
            return

        data = json.loads(body)

        if data['type'] == 1:  # PING
            await send({
                'type': 'http.response.start', 'status': 200,
                'headers': [(b'content-type', b'application/json')]
            })
            await send({'type': 'http.response.body', 'body': b'{"type": 1}'})
            return

        await self.handle_interaction(data, ASGIRequest(scope, receive, send))
