from scripts import qps_federated_docker_lldb_r3 as r5


def test_llvms_failed_to_connect_port_is_retryable() -> None:
    result = {
        "returncode": 1,
        "stdout": "",
        "stderr": "error: Failed to connect port",
    }
    assert r5._explicit_connection_refused(result) is True


def test_os_connection_refused_is_retryable() -> None:
    result = {
        "returncode": 1,
        "stdout": "",
        "stderr": "connect failed: Connection refused",
    }
    assert r5._explicit_connection_refused(result) is True


def test_other_lldb_failure_is_not_retried() -> None:
    result = {
        "returncode": 1,
        "stdout": "",
        "stderr": "error: target create failed",
    }
    assert r5._explicit_connection_refused(result) is False


def test_success_is_never_classified_retryable() -> None:
    result = {
        "returncode": 0,
        "stdout": "error: Failed to connect port was mentioned in fixture text",
        "stderr": "",
    }
    assert r5._explicit_connection_refused(result) is False
