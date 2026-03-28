#!/usr/bin/env python3
"""MCP Reload Proxy — transparent JSON-RPC proxy with hot-reload support.

Usage: python mcp-proxy.py -- <command> [args...]

Wraps any MCP server, forwarding all JSON-RPC messages transparently.
Injects a `reload_server` tool that kills and respawns the child process.
The proxy itself NEVER crashes — only the child process can fail.
"""

import asyncio
import contextlib
import json
import os
import signal
import sys

RELOAD_TOOL = {
    "name": "reload_server",
    "description": "Hot-reload this MCP server (kills and respawns the child process).",
    "inputSchema": {"type": "object", "properties": {}, "required": []},
}


class MCPProxy:
    def __init__(self, child_cmd: list[str]):
        self.child_cmd = child_cmd
        self.child: asyncio.subprocess.Process | None = None
        self.init_msg: str | None = None
        self.pending_list_ids: set = set()
        self._stdout_lock = asyncio.Lock()
        self._child_lock = asyncio.Lock()
        self._reloading = False
        self._child_alive = False
        self._buffer: list[bytes] = []
        self._forward_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._pending_requests: dict[str | int, bool] = {}  # id -> True

    async def _write_stdout(self, data: bytes):
        try:
            async with self._stdout_lock:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        except Exception:
            pass

    async def _write_child(self, data: bytes):
        async with self._child_lock:
            try:
                if self.child and self.child.returncode is None:
                    self.child.stdin.write(data)  # type: ignore[union-attr]
                    await self.child.stdin.drain()  # type: ignore[union-attr]
                    return True
            except Exception:
                pass
        return False

    async def _send_error(self, req_id, msg: str):
        if req_id is None:
            return
        err = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32603, "message": msg},
                }
            )
            + "\n"
        )
        await self._write_stdout(err.encode())

    async def start_child(self, start_tasks=True):
        self.child = await asyncio.create_subprocess_exec(
            *self.child_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ},
        )
        self._child_alive = True
        if start_tasks:
            self._start_background_tasks()

    def _start_background_tasks(self):
        self._forward_task = asyncio.create_task(self._forward_child_stdout())
        self._stderr_task = asyncio.create_task(self._forward_child_stderr())
        self._watchdog_task = asyncio.create_task(self._watch_child())

    async def _stop_background_tasks(self):
        for t in (self._forward_task, self._stderr_task, self._watchdog_task):
            if t:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        self._forward_task = self._stderr_task = self._watchdog_task = None

    async def kill_child(self):
        self._child_alive = False
        if self.child and self.child.returncode is None:
            try:
                self.child.terminate()
                await asyncio.wait_for(self.child.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.child.kill()
                await self.child.wait()
            except Exception:
                pass
        self.child = None

    async def _watch_child(self):
        """Detect child crash and auto-restart (unless we're already reloading)."""
        try:
            if self.child:
                await self.child.wait()
            self._child_alive = False
            if self._reloading:
                return
            print("[mcp-proxy] child crashed, draining pending requests and restarting", file=sys.stderr)
            # Error out all pending requests
            for rid in list(self._pending_requests):
                await self._send_error(rid, "Child process crashed")
            self._pending_requests.clear()
            # Auto-restart
            await self._stop_forward_tasks()
            await self.start_child(start_tasks=False)
            await self.reinit_child()
            self._start_background_tasks()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[mcp-proxy] watchdog error: {e}", file=sys.stderr)

    async def _stop_forward_tasks(self):
        """Stop only forward/stderr tasks (not watchdog)."""
        for t in (self._forward_task, self._stderr_task):
            if t:
                t.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await t
        self._forward_task = self._stderr_task = None

    async def reinit_child(self):
        if not self.init_msg or not self.child:
            return
        if not await self._write_child((self.init_msg + "\n").encode()):
            return
        try:
            await asyncio.wait_for(self.child.stdout.readline(), timeout=10)  # type: ignore[union-attr]
        except Exception:
            return
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        await self._write_child((notif + "\n").encode())

    async def _forward_child_stdout(self):
        try:
            while self.child and self.child.returncode is None:
                line = await self.child.stdout.readline()  # type: ignore[union-attr]
                if not line:
                    break
                try:
                    msg = json.loads(line)
                    rid = msg.get("id")
                    # Remove from pending if it's a response
                    if rid is not None and "method" not in msg:
                        self._pending_requests.pop(rid, None)
                    if rid in self.pending_list_ids:
                        self.pending_list_ids.discard(rid)
                        if "result" in msg and "tools" in msg["result"]:
                            msg["result"]["tools"].append(RELOAD_TOOL)
                        line = (json.dumps(msg) + "\n").encode()
                except (json.JSONDecodeError, KeyError):
                    pass
                await self._write_stdout(line)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[mcp-proxy] child stdout error: {e}", file=sys.stderr)

    async def _forward_child_stderr(self):
        try:
            while self.child and self.child.returncode is None:
                line = await self.child.stderr.readline()  # type: ignore[union-attr]
                if not line:
                    break
                sys.stderr.buffer.write(line)
                sys.stderr.buffer.flush()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def _do_reload(self, req_id):
        self._reloading = True
        try:
            await self._stop_background_tasks()
            # Error out pending requests from before reload
            for rid in list(self._pending_requests):
                await self._send_error(rid, "Server reloading, request cancelled")
            self._pending_requests.clear()
            await self.kill_child()
            await self.start_child(start_tasks=False)
            await self.reinit_child()
            self._start_background_tasks()
            resp = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"content": [{"type": "text", "text": "Server reloaded successfully."}]},
                    }
                )
                + "\n"
            )
            await self._write_stdout(resp.encode())
            notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}) + "\n"
            await self._write_stdout(notif.encode())
        except Exception as e:
            err = (
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32603, "message": f"Reload failed: {e}"},
                    }
                )
                + "\n"
            )
            await self._write_stdout(err.encode())
        finally:
            buf, self._buffer = self._buffer, []
            self._reloading = False
            for line in buf:
                await self._write_child(line)

    async def run(self):
        await self.start_child()

        loop = asyncio.get_event_loop()
        stdin_reader = asyncio.StreamReader()
        await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(stdin_reader), sys.stdin.buffer)

        while True:
            try:
                line = await stdin_reader.readline()
                if not line:
                    break
                raw = line.decode().strip()
                if not raw:
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    if not self._reloading:
                        await self._write_child(line)
                    else:
                        self._buffer.append(line)
                    continue

                method = msg.get("method", "")
                req_id = msg.get("id")

                if method == "initialize":
                    self.init_msg = raw

                if method == "tools/list" and req_id is not None:
                    self.pending_list_ids.add(req_id)

                # Handle reload_server
                if method == "tools/call" and msg.get("params", {}).get("name") == "reload_server":
                    await self._do_reload(req_id)
                    continue

                # Track requests that expect responses
                if req_id is not None and method:
                    self._pending_requests[req_id] = True

                # Buffer during reload, otherwise forward
                if self._reloading:
                    self._buffer.append(line)
                elif not self._child_alive:
                    await self._send_error(req_id, "Child process is down")
                else:
                    ok = await self._write_child(line)
                    if not ok and req_id is not None:
                        self._pending_requests.pop(req_id, None)
                        await self._send_error(req_id, "Failed to write to child process")

            except Exception as e:
                print(f"[mcp-proxy] main loop error: {e}", file=sys.stderr)
                continue  # NEVER die

        await self._stop_background_tasks()
        await self.kill_child()


def main():
    if "--" not in sys.argv:
        print("Usage: python mcp-proxy.py -- <command> [args...]", file=sys.stderr)
        sys.exit(1)
    child_cmd = sys.argv[sys.argv.index("--") + 1 :]
    if not child_cmd:
        print("No child command specified after --", file=sys.stderr)
        sys.exit(1)

    proxy = MCPProxy(child_cmd)

    # Graceful signals — don't kill the proxy, just ignore
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    try:
        asyncio.run(proxy.run())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception as e:
        print(f"[mcp-proxy] fatal: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
