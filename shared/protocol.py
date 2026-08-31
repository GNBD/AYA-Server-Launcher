import json

ENCODING = "utf-8"


def encode(msg: dict) -> bytes:
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode(ENCODING)


async def send(writer, msg: dict) -> None:
    writer.write(encode(msg))
    await writer.drain()


async def recv(reader) -> dict | None:
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode(ENCODING))