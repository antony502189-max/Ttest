"""Only CONNECT api.deepseek.com:443. TLS stays end-to-end in the backend.

Only this proxy has an external Docker network; backend has only internal.
No payload/key logging, no DNS/URL selected by the caller, bounded connections.
"""
import asyncio
from contextlib import suppress


async def pipe(reader, writer):
    while data := await reader.read(16384):
        writer.write(data)
        await writer.drain()


async def connect(reader, writer):
    upstream = None
    try:
        async with asyncio.timeout(20):
            head = await reader.readuntil(b"\r\n\r\n")
            if len(head) > 4096 or head.split(b"\r\n", 1)[0] != b"CONNECT api.deepseek.com:443 HTTP/1.1":
                writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
                await writer.drain()
                return
            remote, upstream = await asyncio.open_connection("api.deepseek.com", 443)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            tasks = [asyncio.create_task(pipe(reader, upstream)), asyncio.create_task(pipe(remote, writer))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
    except (TimeoutError, OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        pass
    finally:
        for stream in (upstream, writer):
            if stream:
                stream.close()
                with suppress(OSError):
                    await stream.wait_closed()


async def main():
    server = await asyncio.start_server(connect, "0.0.0.0", 3128, limit=4096)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
