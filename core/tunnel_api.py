import asyncio
import json
import sys
import threading
import time
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from shared.protocol import send, recv
from shared.relay import relay
from shared.relay import pipe_tcp_to_udp, encode_frame


def _state_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / ".mcnat"
    return Path(__file__).resolve().parent


def _state_file() -> Path:
    d = _state_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "last_host.txt"


def _load_last_host() -> str:
    try:
        f = _state_file()
        if f.exists():
            return f.read_text(encoding="utf-8").strip() or "158.179.168.246"
    except Exception:
        pass
    return "158.179.168.246"


def _save_last_host(host: str) -> None:
    try:
        _state_file().write_text(host.strip(), encoding="utf-8")
    except Exception:
        pass


def _run_async(coro, loop, timeout=15):
    while not loop.is_running():
        time.sleep(0.05)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=timeout)


class ClientApi:
    def __init__(self):
        self.server_host = "158.179.168.246"
        self.server_port = 42137
        self.reader = None
        self.writer = None
        self.loop = asyncio.new_event_loop()
        self.logged_in = False
        self.user_id = None
        self.username = ""
        self.credits = 0
        self.plan_credits = 0
        self.bonus_credits = 0
        self.plan = "free"
        self.is_admin = False
        self.tunnel_active = False
        self.tunnel_id = ""
        self.target_host = "127.0.0.1"
        self.target_port = 25565
        self.public_host = ""
        self.public_port = 0
        self.proto = "tcp"
        self.running = True
        self._reader_task = None
        self._pending = None  # 현재 대기 중인 단일 Future
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _stop_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _connect(self):
        self.reader, self.writer = await asyncio.open_connection(
            self.server_host, self.server_port
        )
        # 세션마다 고유한 터널ID → 다른 세션(클라이언트)과 충돌 방지
        self.tunnel_id = "t" + uuid.uuid4().hex[:8]
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def _disconnect(self):
        if self.writer and not self.writer.is_closing():
            self.writer.close()
        self.writer = None
        self.reader = None
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        self.logged_in = False
        self.tunnel_active = False
        self._pending = None

    async def _reader_loop(self):
        while self.running:
            try:
                msg = await recv(self.reader)
            except (ConnectionError, OSError, ValueError, asyncio.CancelledError):
                break
            if msg is None:
                break
            mtype = msg.get("type")
            if mtype == "CONNECT":
                asyncio.create_task(self._handle_connect(msg))
            elif mtype == "CREDIT_UPDATE":
                self.credits = msg.get("credits", self.credits)
            elif mtype == "CREDIT_WARNING":
                self.credits = msg.get("credits", 0)
            elif mtype == "CREDIT_EXHAUSTED":
                self.tunnel_active = False
            elif mtype == "FORCE_DISCONNECT":
                self.tunnel_active = False
                self.logged_in = False
                break
            elif mtype == "FORCE_TUNNEL_CLOSE":
                if msg.get("tunnel_id") == self.tunnel_id:
                    self.tunnel_active = False
            elif mtype == "PONG":
                pass
            else:
                if self._pending is not None and not self._pending.done():
                    self._pending.set_result(msg)
                self._pending = None

    async def _request(self, msg, timeout=10):
        if self._pending is not None:
            raise RuntimeError("요청이 이미 진행 중입니다")
        future = self.loop.create_future()
        self._pending = future
        try:
            await send(self.writer, msg)
        except Exception:
            self._pending = None
            raise
        try:
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            self._pending = None
            return None

    def get_last_host(self) -> dict:
        return {"success": True, "host": _load_last_host()}

    def save_last_host(self, host) -> dict:
        if host:
            _save_last_host(host)
        return {"success": True}

    def connect(self, server_host=None, server_port=None) -> dict:
        if server_host:
            self.server_host = server_host
        if server_port:
            self.server_port = int(server_port)
        print(f"[클라이언트] 서버 연결 시도: {self.server_host}:{self.server_port}", flush=True)
        try:
            _run_async(self._connect(), self.loop)
            print("[클라이언트] 서버 연결 성공", flush=True)
            return {"success": True}
        except Exception as e:
            print(f"[클라이언트] 서버 연결 실패: {e}", flush=True)
            return {"success": False, "error": str(e)}

    def login(self, username, password) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "LOGIN", "username": username, "password": password}),
                self.loop,
            )
            if resp and resp.get("type") == "LOGIN_OK":
                self.logged_in = True
                self.user_id = resp.get("user_id")
                self.username = resp.get("username", username)
                self.credits = resp.get("credits", 0)
                self.plan_credits = resp.get("plan_credits", 0)
                self.bonus_credits = resp.get("bonus_credits", 0)
                self.plan = resp.get("plan", "free")
                self.is_admin = resp.get("is_admin", False)
                return {"success": True, "data": resp}
            return {"success": False, "error": resp.get("reason", "로그인 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_tunnel(self, target_host, target_port, proto="tcp") -> dict:
        try:
            self.target_host = target_host
            self.target_port = int(target_port)
            self.proto = proto
            resp = _run_async(
                self._request({
                    "type": "CREATE",
                    "tunnel_id": self.tunnel_id,
                    "target_host": target_host,
                    "target_port": int(target_port),
                    "proto": proto,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "CREATE_OK":
                self.tunnel_active = True
                self.public_host = resp.get("public_host") or self.server_host
                self.public_port = resp.get("public_port")
                self.proto = resp.get("proto", proto)
                return {"success": True, "address": f"{self.public_host}:{self.public_port}"}
            return {"success": False, "error": resp.get("reason", "생성 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_tunnel(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "DELETE", "tunnel_id": self.tunnel_id}),
                self.loop,
            )
            if resp and resp.get("type") == "DELETE_OK":
                self.tunnel_active = False
                self.public_host = ""
                self.public_port = 0
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "종료 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_status(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "GET_STATUS"}),
                self.loop,
            )
            if resp and resp.get("type") == "STATUS":
                self.credits = resp.get("credits", self.credits)
                self.plan_credits = resp.get("plan_credits", self.plan_credits)
                self.bonus_credits = resp.get("bonus_credits", self.bonus_credits)
                self.plan = resp.get("plan", self.plan)
                return {"success": True, "credits": self.credits, "plan": self.plan, "session_count": resp.get("session_count", 0)}
            return {"success": False, "error": "상태 조회 실패"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_notice(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "GET_NOTICE"}),
                self.loop,
            )
            if resp and resp.get("type") == "NOTICE":
                return {
                    "success": True,
                    "notice": resp.get("notice", ""),
                    "notice_id": resp.get("notice_id", 0),
                }
            return {"success": False, "error": "공지 조회 실패"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_notice(self, notice) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "SET_NOTICE", "notice": notice}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_NOTICE_SET":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "공지 설정 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_connections(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "GET_CONNECTIONS"}),
                self.loop,
            )
            if resp and resp.get("type") == "CONNECTION_LIST":
                return {"success": True, "connections": resp.get("connections", [])}
            return {"success": False, "error": "접속자 조회 실패"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def kick_connection(self, conn_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "KICK_CONNECTION", "conn_id": conn_id}),
                self.loop,
            )
            if resp and resp.get("type") == "KICK_CONNECTION_OK":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "끊기 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_tunnel_info(self) -> dict:
        return {
            "success": True,
            "logged_in": self.logged_in,
            "tunnel_active": self.tunnel_active,
            "public_address": f"{self.public_host}:{self.public_port}" if self.tunnel_active else "",
            "credits": self.credits,
            "plan_credits": self.plan_credits,
            "bonus_credits": self.bonus_credits,
            "username": self.username,
            "plan": self.plan,
            "is_admin": self.is_admin,
            "proto": getattr(self, "proto", "tcp"),
        }

    def request_plan(self, plan) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "REQUEST_PLAN", "plan": plan}),
                self.loop,
            )
            if resp and resp.get("type") == "REQUEST_PLAN_OK":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "신청 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_plan_requests(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "LIST_PLAN_REQUESTS"}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_PLAN_REQUEST_LIST":
                return {"success": True, "requests": resp.get("requests", [])}
            return {"success": False, "error": resp.get("reason", "조회 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def resolve_plan_request(self, request_id, approve) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "RESOLVE_PLAN_REQUEST",
                    "request_id": request_id,
                    "approve": approve,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_PLAN_REQUEST_RESOLVED":
                return {"success": True, "result": resp.get("result")}
            return {"success": False, "error": resp.get("reason", "처리 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_plan(self, user_id, plan) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "SET_PLAN",
                    "user_id": user_id,
                    "plan": plan,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_PLAN_SET":
                return {"success": True, "plan": resp.get("plan")}
            return {"success": False, "error": resp.get("reason", "변경 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def change_password(self, old_password, new_password) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "CHANGE_PASSWORD",
                    "old_password": old_password,
                    "new_password": new_password,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "CHANGE_PASSWORD_OK":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "변경 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_password(self, user_id, new_password) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "SET_PASSWORD",
                    "user_id": user_id,
                    "new_password": new_password,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_PASSWORD_CHANGED":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "비밀번호 변경 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_users(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "LIST_USERS"}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_LIST":
                return {"success": True, "users": resp.get("users", [])}
            return {"success": False, "error": resp.get("reason", "조회 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_user(self, username, password, credits=0) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "CREATE_USER",
                    "username": username,
                    "password": password,
                    "credits": int(credits),
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_CREATED":
                return {"success": True, "user": resp.get("user")}
            return {"success": False, "error": resp.get("reason", "생성 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_user(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "DELETE_USER", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_DELETED":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "삭제 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def add_credits(self, user_id, amount) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "ADD_CREDITS",
                    "user_id": user_id,
                    "amount": int(amount),
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_CREDITS_UPDATED":
                return {"success": True, "new_balance": resp.get("new_balance")}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_credits(self, user_id, amount) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "REMOVE_CREDITS",
                    "user_id": user_id,
                    "amount": int(amount),
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_CREDITS_UPDATED":
                return {"success": True, "new_balance": resp.get("new_balance")}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_credits(self, user_id, amount) -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "SET_CREDITS",
                    "user_id": user_id,
                    "amount": int(amount),
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_CREDITS_UPDATED":
                return {"success": True, "new_balance": resp.get("new_balance")}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ban_user(self, user_id, reason="") -> dict:
        try:
            resp = _run_async(
                self._request({
                    "type": "ADMIN_ACTION",
                    "action": "BAN_USER",
                    "user_id": user_id,
                    "reason": reason,
                }),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_BANNED":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "밴 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def unban_user(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "UNBAN_USER", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_UNBANNED":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def force_disconnect(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "FORCE_DISCONNECT", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_DISCONNECTED":
                return {"success": True, "count": resp.get("count", 0)}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def force_close_tunnels(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "FORCE_CLOSE_TUNNELS", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_TUNNELS_CLOSED":
                return {"success": True, "count": resp.get("count", 0)}
            return {"success": False, "error": resp.get("reason", "실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def start_background_tasks(self):
        asyncio.run_coroutine_threadsafe(self._keepalive_loop(), self.loop)

    async def _keepalive_loop(self):
        while self.running and self.logged_in:
            await asyncio.sleep(30)
            if self.writer and not self.writer.is_closing():
                try:
                    await send(self.writer, {"type": "PING"})
                except (ConnectionError, OSError):
                    break

    async def _handle_connect(self, msg):
        tunnel_id = msg.get("tunnel_id", "")
        conn_id = msg.get("conn_id", "")
        proto = msg.get("proto", "tcp")
        if tunnel_id != self.tunnel_id:
            return
        data_writer = None
        target_writer = None
        try:
            data_reader, data_writer = await asyncio.open_connection(
                self.server_host, self.server_port
            )
            await send(data_writer, {"type": "DATA", "conn_id": conn_id})
        except (ConnectionError, OSError) as e:
            if data_writer:
                try:
                    data_writer.close()
                except Exception:
                    pass
            return

        if proto == "udp":
            # UDP 타겟: 큐 기반 DatagramProtocol 사용
            from shared.relay import decode_frames
            loop = asyncio.get_event_loop()
            recv_queue: asyncio.Queue = asyncio.Queue(maxsize=1024)

            class _TargetProto(asyncio.DatagramProtocol):
                def connection_made(self, transport):
                    pass
                def datagram_received(self, data, addr):
                    try:
                        recv_queue.put_nowait(data)
                    except asyncio.QueueFull:
                        pass
                def error_received(self, exc):
                    pass

            try:
                target_transport, _ = await loop.create_datagram_endpoint(
                    _TargetProto,
                    remote_addr=(self.target_host, int(self.target_port)),
                )
            except (ConnectionError, OSError):
                try:
                    data_writer.close()
                except Exception:
                    pass
                return

            # TCP(서버) → UDP(타겟) 방향: 프레임 읽어 타겟으로 전송
            async def _tcp_to_target():
                buf = b""
                try:
                    while True:
                        chunk = await data_reader.read(65536)
                        if not chunk:
                            break
                        buf += chunk
                        frames, buf = decode_frames(buf)
                        for frame in frames:
                            target_transport.sendto(frame)
                except (ConnectionError, asyncio.CancelledError, OSError):
                    pass
                except Exception:
                    pass
                finally:
                    try:
                        target_transport.close()
                    except Exception:
                        pass
                    try:
                        data_writer.close()
                    except Exception:
                        pass

            # UDP(타겟) → TCP(서버) 방향: 수신한 데이터그램을 프레임으로 서버에 기록
            async def _target_to_tcp():
                try:
                    while True:
                        data = await recv_queue.get()
                        if data is None:
                            break
                        frame = encode_frame(data)
                        data_writer.write(frame)
                        await data_writer.drain()
                except (ConnectionError, asyncio.CancelledError, OSError):
                    pass
                except Exception:
                    pass
                finally:
                    try:
                        target_transport.close()
                    except Exception:
                        pass
                    try:
                        data_writer.close()
                    except Exception:
                        pass

            await asyncio.gather(_tcp_to_target(), _target_to_tcp())
        else:
            # TCP 타겟: 기존 로직 (변경 없음)
            try:
                target_reader, target_writer = await asyncio.open_connection(
                    self.target_host, int(self.target_port)
                )
            except (ConnectionError, OSError) as e:
                try:
                    data_writer.close()
                except Exception:
                    pass
                return
            await relay(data_reader, data_writer, target_reader, target_writer)

    def disconnect(self):
        """로그아웃: 연결만 끊고 루프는 유지해 재로그인 가능하게 한다."""
        try:
            _run_async(self._disconnect(), self.loop)
        except Exception:
            pass

    def get_user_log(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "GET_USER_LOG", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_LOG":
                return {"success": True, "log": resp.get("log", ""), "username": resp.get("username", "")}
            return {"success": False, "error": resp.get("reason", "조회 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_user_logs(self) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "LIST_USER_LOGS"}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_LOG_LIST":
                return {"success": True, "logs": resp.get("logs", [])}
            return {"success": False, "error": resp.get("reason", "조회 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_user_log(self, user_id) -> dict:
        try:
            resp = _run_async(
                self._request({"type": "ADMIN_ACTION", "action": "DELETE_USER_LOG", "user_id": user_id}),
                self.loop,
            )
            if resp and resp.get("type") == "ADMIN_USER_LOG_DELETED":
                return {"success": True}
            return {"success": False, "error": resp.get("reason", "삭제 실패") if resp else "응답 없음"}
        except Exception as e:
            return {"success": False, "error": str(e)}
