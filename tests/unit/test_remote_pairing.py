"""Remote pairing: what a failure says on the screen."""

import pytest

from couchbox import remote


@pytest.mark.parametrize(
    "error, says",
    [
        ("org.bluez.Error.AuthenticationCanceled: Authentication Canceled", "turned the pairing down"),
        ("org.bluez.Error.Failed: Page Timeout", "stopped answering"),
        ("timed out", "stopped answering"),
        ("org.bluez.Error.ConnectionAttemptFailed: Page Timeout", "stopped answering"),
        ("org.bluez.Error.NotReady: Resource Not Ready", "Bluetooth isn't working"),
        ("not found", "No remote in pairing mode"),
        ("org.bluez.Error.Something", "didn't finish"),
    ],
)
def test_failures_say_what_happened(error, says):
    assert says in remote.why(error)
