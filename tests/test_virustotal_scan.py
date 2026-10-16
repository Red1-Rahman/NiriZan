import hashlib
import importlib.util
from email import policy
from email.parser import BytesParser
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def scanner(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("VT_API_KEY", "synthetic-test-key")
    path = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "virustotal_scan.py"
    spec = importlib.util.spec_from_file_location("virustotal_scan", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module.urllib.request, "urlopen", Mock(side_effect=AssertionError("network"))
    )
    monkeypatch.setattr(module.time, "sleep", Mock(side_effect=AssertionError("sleep")))
    return module


@pytest.mark.parametrize("filename", ["artifact.whl", "niri-পরীক্ষা-é.whl"])
@pytest.mark.parametrize("payload", [b"", b"\x00\xff\xfe\r\nbinary\x80"])
def test_upload_preserves_utf8_filename_and_binary_payload(
    scanner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    payload: bytes,
) -> None:
    directory = tmp_path / "nested"
    directory.mkdir()
    artifact = directory / filename
    artifact.write_bytes(payload)
    request = Mock(side_effect=[(404, {}), (200, {"data": {"id": "analysis-id"}})])
    poll = Mock(return_value={"malicious": 0})
    monkeypatch.setattr(scanner, "make_vt_request", request)
    monkeypatch.setattr(scanner, "poll_analysis", poll)

    scanner.scan_file(str(artifact))

    assert request.call_count == 2
    file_hash = hashlib.sha256(payload).hexdigest()
    assert request.call_args_list[0].args == (
        f"https://www.virustotal.com/api/v3/files/{file_hash}",
    )
    upload = request.call_args_list[1]
    assert upload.args == ("https://www.virustotal.com/api/v3/files",)
    assert upload.kwargs["method"] == "POST"
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {upload.kwargs['content_type']}\r\nMIME-Version: 1.0\r\n\r\n".encode(
            "ascii"
        )
        + upload.kwargs["data"]
    )
    assert message.get_content_type() == "multipart/form-data"
    assert not message.defects
    parts = list(message.iter_parts())
    assert len(parts) == 1
    part = parts[0]
    assert part.get_param("name", header="content-disposition") == "file"
    assert part.get_filename() == filename
    assert part.get_content_type() == "application/octet-stream"
    assert part.get_payload(decode=True) == payload
    poll.assert_called_once_with("analysis-id")


@pytest.mark.parametrize("status", [403, 500])
def test_failed_upload_exits_without_polling(
    scanner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    artifact = tmp_path / "artifact.whl"
    artifact.write_bytes(b"\xff\x00")
    request = Mock(side_effect=[(404, {}), (status, {"error": "upload failed"})])
    poll = Mock()
    monkeypatch.setattr(scanner, "make_vt_request", request)
    monkeypatch.setattr(scanner, "poll_analysis", poll)

    with pytest.raises(SystemExit) as error:
        scanner.scan_file(str(artifact))

    assert error.value.code == 1
    assert request.call_count == 2
    poll.assert_not_called()
