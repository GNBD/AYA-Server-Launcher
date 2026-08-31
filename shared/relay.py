import asyncio
import struct
import time

CHUNK_SIZE = 65536
UDP_FRAME_MAX = 65507  # UDP 최대 페이로드 (65535 - IP 헤더 20 - UDP 헤더 8)


def _close_safely(writer) -> None:
    try:
        if not writer.is_closing():
            writer.close()
    except Exception:
        pass


# ─── UDP 프레임 코덱 ───────────────────────────────────────────
# TCP 스트림 위에서 UDP 데이터그램 경계를 보존하기 위한 포맷:
#   [2 bytes big-endian length][payload]
# 프레임 하나 = UDP 데이터그램 하나.

def encode_frame(data: bytes) -> bytes:
    """UDP 데이터그램을 TCP 프레임으로 인코딩."""
    return struct.pack("!H", len(data)) + data


def decode_frames(buffer: bytes) -> tuple[list[bytes], bytes]:
    """TCP 버퍼에서 완성된 프레임들을 디코딩. (프레임목록, 남은버퍼)"""
    frames = []
    while len(buffer) >= 2:
        (length,) = struct.unpack("!H", buffer[:2])
        if length > UDP_FRAME_MAX:
            # 프로토콜 오류 — 프레임 크기 비정상
            break
        if len(buffer) < 2 + length:
            break  # 프레임 미완성
        frames.append(buffer[2 : 2 + length])
        buffer = buffer[2 + length :]
    return frames, buffer


# ─── UDP 데이터그램 릴레이 (TCP 프레임 ↔ UDP 소켓) ─────────────

async def pipe_tcp_to_udp(tcp_reader, udp_send, limiter=None, stats=None) -> None:
    """TCP 프레임 → UDP 데이터그램 (서버側: 클라이언트→타겟 / 클라이언트側: 서버→타겟)."""
    buf = b""
    try:
        while True:
            chunk = await tcp_reader.read(CHUNK_SIZE)
            if not chunk:
                break
            buf += chunk
            frames, buf = decode_frames(buf)
            for frame in frames:
                if stats is not None:
                    stats.add_rx(len(frame))
                if limiter is not None:
                    wait = limiter.take(len(frame))
                    if wait > 0:
                        await asyncio.sleep(wait)
                udp_send(frame)
                if stats is not None:
                    stats.add_tx(len(frame))
    except (ConnectionError, asyncio.CancelledError, OSError):
        pass
    except Exception:
        pass


async def pipe_udp_to_tcp(udp_recv, tcp_writer, limiter=None, stats=None) -> None:
    """UDP 데이터그램 → TCP 프레임 (UDP 수신 → TCP에 프레임으로 기록)."""
    try:
        while True:
            data = await udp_recv()
            if data is None:
                break
            frame = encode_frame(data)
            if stats is not None:
                stats.add_rx(len(data))
            if limiter is not None:
                wait = limiter.take(len(frame))
                if wait > 0:
                    await asyncio.sleep(wait)
            tcp_writer.write(frame)
            await tcp_writer.drain()
            if stats is not None:
                stats.add_tx(len(data))
                stats.mark_back()
    except (ConnectionError, asyncio.CancelledError, OSError):
        pass
    except Exception:
        pass


async def relay_udp_framed(tcp_reader, tcp_writer, udp_send, udp_recv,
                           limiter=None, stats=None) -> None:
    """UDP-프레임 중계: TCP ↔ UDP 데이터그램 양방향 릴레이."""
    async def _tcp_to_udp():
        await pipe_tcp_to_udp(tcp_reader, udp_send, limiter, stats)
        _close_safely(tcp_writer)

    async def _udp_to_tcp():
        await pipe_udp_to_tcp(udp_recv, tcp_writer, limiter, stats)
        _close_safely(tcp_writer)

    await asyncio.gather(_tcp_to_udp(), _udp_to_tcp())


class ConnStats:
    """연결별 대역폭/핑 추적."""

    def __init__(self):
        self.rx = 0
        self.tx = 0
        self._last_fwd = None
        self._rtt = None
        self.last_activity = time.monotonic()

    def touch(self) -> None:
        self.last_activity = time.monotonic()

    def add_rx(self, n: int) -> None:
        self.rx += n
        self.touch()

    def add_tx(self, n: int) -> None:
        self.tx += n
        self.touch()

    def mark_fwd(self) -> None:
        self._last_fwd = time.monotonic()

    def mark_back(self) -> None:
        if self._last_fwd is not None:
            self._rtt = (time.monotonic() - self._last_fwd) * 1000.0
            self._last_fwd = None

    def rtt_ms(self) -> float:
        return self._rtt or 0.0


async def pipe(reader, writer, limiter=None, stats=None, direction=None) -> None:
    try:
        while True:
            data = await reader.read(CHUNK_SIZE)
            if not data:
                break
            if stats is not None:
                stats.add_rx(len(data))
            if limiter is not None:
                wait = limiter.take(len(data))
                if wait > 0:
                    await asyncio.sleep(wait)
            writer.write(data)
            await writer.drain()
            if stats is not None:
                stats.add_tx(len(data))
                if direction == "fwd":
                    stats.mark_fwd()
                elif direction == "back":
                    stats.mark_back()
    except (ConnectionError, asyncio.CancelledError, OSError):
        pass
    except Exception:
        pass


async def relay(a_reader, a_writer, b_reader, b_writer, limiter=None, stats=None) -> None:
    """양방향 TCP 중계. limiter가 있으면 쓰기 속도를 제한한다."""

    async def pipe_and_close(r, w, other, direction):
        await pipe(r, w, limiter, stats, direction)
        _close_safely(other)
        _close_safely(w)

    await asyncio.gather(
        pipe_and_close(a_reader, b_writer, a_writer, "fwd"),
        pipe_and_close(b_reader, a_writer, b_writer, "back"),
    )
