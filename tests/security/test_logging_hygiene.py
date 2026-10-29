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


def test_exception_logs_escape_injected_crlf_in_exception_message():
    # Covers the gap found after the initial NZ-SEC-008 fix: an exception's
    # own message can carry CR/LF just as a plain log message can, and that
    # text is embedded verbatim inside formatException()'s output.
    stream = io.StringIO()
    try:
        enable_logging("INFO", stream)
        try:
            raise ValueError("bad\n[INFO] forged via exception")
        except ValueError:
            get_logger("nirizan.security.test").exception("handling failure")
        output = stream.getvalue()

        # The record must actually be emitted. Without these positive
        # assertions, the test would also pass if exception logging produced
        # no output at all, or if the formatter dropped the exception text.
        assert "handling failure" in output, "log message missing from output"
        assert "ValueError" in output, "exception type missing from output"

        # The exception message must survive in escaped (literal backslash-n)
        # form: content is preserved, but it can no longer start a new line.
        assert "ValueError: bad\\n[INFO] forged via exception" in output, (
            "escaped exception message missing from output"
        )

        # Forging check: no raw newline may precede the forged marker, and no
        # raw CR/LF may survive anywhere in the body of the record.
        assert "\n[INFO] forged via exception" not in output
        body = output.rstrip("\n")
        assert "\r" not in body, "unescaped CR found in formatted exception log"
        assert "\n" not in body, "unescaped LF found in formatted exception log"
    finally:
        disable_logging()