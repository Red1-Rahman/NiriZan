import io

from nirizan._logging import disable_logging, enable_logging, get_logger


def test_formatted_logs_escape_injected_crlf():
    stream = io.StringIO()
    try:
        enable_logging("INFO", stream)
        get_logger("nirizan.security.test").info("safe\r\n[ERROR] forged")
        output = stream.getvalue()
        assert "\r\n" not in output
    finally:
        disable_logging()
