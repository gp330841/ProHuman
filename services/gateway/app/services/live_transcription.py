"""Stream an optional caption preview without coupling it to audio durability."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

from contextlib import suppress

import structlog
from websockets.asyncio.client import connect

logger = structlog.get_logger(__name__)


class LiveTranscription:
    def __init__(self, api_key: str, language: str, send: Callable[[dict], Awaitable[None]]):
        self.audio: asyncio.Queue[bytes] = asyncio.Queue(maxsize=32)
        self.send = send
        self.task = asyncio.create_task(self._stream(api_key, language))

    def append(self, data: bytes) -> None:
        if self.task.done():
            return
        try:
            self.audio.put_nowait(data)
        except asyncio.QueueFull:
            self.task.cancel()

    async def close(self) -> None:
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def _stream(self, api_key: str, language: str) -> None:
        try:
            params = urlencode({
                "model": "nova-3", "language": language, "interim_results": "true", "smart_format": "true",
            })
            async with connect(
                "wss://api.deepgram.com/v1/listen?" + params,
                additional_headers={"Authorization": "Token " + api_key},
                open_timeout=5,
                close_timeout=1,
            ) as upstream:
                async def forward_audio():
                    while True:
                        try:
                            data = await asyncio.wait_for(self.audio.get(), timeout=5)
                            await upstream.send(data)
                        except TimeoutError:
                            await upstream.send('{"type":"KeepAlive"}')

                async def forward_captions():
                    async for message in upstream:
                        result = json.loads(message)
                        alternatives = result.get("channel", {}).get("alternatives", [])
                        if alternatives and alternatives[0].get("transcript"):
                            await self.send({
                                "type": "caption", "text": alternatives[0]["transcript"],
                                "final": result.get("is_final", False),
                            })

                tasks = [asyncio.create_task(forward_audio()), asyncio.create_task(forward_captions())]
                try:
                    done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as exc:
            logger.info("live_captions_unavailable", error_type=type(exc).__name__)
            with suppress(Exception):
                await self.send({"type": "caption_unavailable"})
