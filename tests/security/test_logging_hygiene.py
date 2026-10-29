import io

from nirizan._logging import disable_logging, enable_logging, get_logger


def test_formatted_logs_escape_injected_crlf():
    # Finding NZ-SEC-008 (fixed): a message containing CR/LF must not produce
    # more than one line in the formatted output. Checking only "\r\n" is not
    # enough -- a fix that escapes \r but leaves bare \n untouched would still
    # let "safe\n[ERROR] forged" render as two separate lines. Assert neither
    # a standalone \r nor a standalone \n survives unescaped in the body.
    stream = io.StringIO()
    try:
        enable_logging("INFO", stream)
        get_logger("nirizan.security.test").info("safe\r\n[ERROR] forged")
        output = stream.getvalue()

        # The one real newline allowed is the trailing terminator StreamHandler
        # appends after each record; everything else must be escaped.
        body = output.rstrip("\n")
        assert "\r" not in body, "unescaped CR found in formatted log body"
        assert "\n" not in body, "unescaped LF found in formatted log body"

        # The record should still render as exactly one logical log line.
        assert output.count("[INFO]") == 1
    finally:
        disable_logging()


def test_formatted_logs_escape_standalone_lf_without_cr():
    # Separately exercise bare \n (no accompanying \r), since a formatter
    # that only strips/escapes \r\n pairs would miss this case entirely.
    stream = io.StringIO()
    try:
        enable_logging("INFO", stream)
        get_logger("nirizan.security.test").info("safe\n[ERROR] forged")
        output = stream.getvalue()

        body = output.rstrip("\n")
        assert "\n" not in body, "unescaped bare LF found in formatted log body"
        assert output.count("[INFO]") == 1
    finally:
        disable_logging()
