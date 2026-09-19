from agent import BugSenseAgent


def test_retryable_timeout():
    assert BugSenseAgent._is_retryable(TimeoutError("read timed out"))


def test_non_retryable_auth_error():
    assert not BugSenseAgent._is_retryable(RuntimeError("API key not valid"))
