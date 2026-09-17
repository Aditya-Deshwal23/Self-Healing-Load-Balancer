import asyncio

from shlb_api.worker_io import HAProxyRuntime, HAProxyRuntimeError


STAT = (
    "# pxname,svname,qcur,qmax,scur,rtime,hrsp_5xx,weight,lastchg"
)


def row(server: str, *, rtime: str = "20", errors: str = "4") -> str:
    values = ["-"] * len(STAT.split(","))
    headers = [header.strip() for header in STAT[2:].split(",")]
    values[headers.index("pxname")] = "be_checkout"
    values[headers.index("svname")] = server
    values[headers.index("qcur")] = "3"
    values[headers.index("scur")] = "7"
    values[headers.index("rtime")] = rtime
    values[headers.index("weight")] = "100"
    values[headers.index("hrsp_5xx")] = errors
    return ",".join(values)


class FakeWriter:
    def __init__(self):
        self.closed = False
        self.payload = b""

    def write(self, payload: bytes) -> None:
        self.payload += payload

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class FakeReader:
    def __init__(self, chunks: list[bytes]):
        self.chunks = iter(chunks)

    async def read(self, _size: int) -> bytes:
        return next(self.chunks, b"")


def test_async_command_accumulates_chunks_and_closes(monkeypatch):
    writer = FakeWriter()
    reader = FakeReader([b"first\n", b"second\n", b""])

    async def open_connection(_path: str):
        return reader, writer

    monkeypatch.setattr("shlb_api.worker_io.asyncio.open_unix_connection", open_connection)
    runtime = HAProxyRuntime("/tmp/admin.sock")
    result = asyncio.run(runtime.async_command("show stat"))

    assert result == "first\nsecond\n"
    assert writer.payload == b"show stat\n"
    assert writer.closed is True


def test_parser_maps_missing_metrics_to_none_and_skips_aggregates():
    runtime = HAProxyRuntime()
    raw = STAT + "\n" + row("BACKEND") + "\n" + row("srv_inst_a", rtime="-", errors="-") + "\n"
    parsed = runtime._parse_fast_samples(raw)

    assert list(parsed) == ["checkout/inst-a"]
    assert parsed["checkout/inst-a"]["latency_ms"] is None
    assert parsed["checkout/inst-a"]["errors_5xx"] is None
    assert parsed["checkout/inst-a"]["queue"] == 3


def test_counter_reset_is_discarded_not_emitted_as_negative_rate():
    runtime = HAProxyRuntime()
    first = STAT + "\n" + row("srv_inst_a", errors="10") + "\n"
    second = STAT + "\n" + row("srv_inst_a", errors="2") + "\n"

    runtime._parse_fast_samples(first)
    parsed = runtime._parse_fast_samples(second)

    assert parsed["checkout/inst-a"]["counter_reset"] is True
    assert "errors_5xx_delta" not in parsed["checkout/inst-a"]


def test_timeout_is_explicit(monkeypatch):
    async def open_connection(_path: str):
        raise asyncio.TimeoutError

    monkeypatch.setattr("shlb_api.worker_io.asyncio.open_unix_connection", open_connection)
    runtime = HAProxyRuntime()

    try:
        asyncio.run(runtime.async_command("show stat"))
    except HAProxyRuntimeError as exc:
        assert "timeout" in str(exc).lower()
    else:
        raise AssertionError("timeout must surface as HAProxyRuntimeError")
