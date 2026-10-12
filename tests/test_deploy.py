import subprocess
import os
import textwrap


def run(cmd, check=True, capture_output=True, text=True):
    """Utility wrapper around subprocess.run
    ensuring a consistent call surface across the test.
    """
    return subprocess.run(cmd, shell=True, check=check,
                          capture_output=capture_output, text=text)


def test_deploy_and_smoke():
    # 1. Run the deploy script. It should exit with 0.
    out = run("./scripts/deploy.sh", capture_output=True)
    assert out.returncode == 0, f"deploy.sh failed: {out.stderr}"

    # 2. Give services a moment to start.  In the testing environment
    # we avoid sophisticated waits; the smoke test will simply retry a
    # couple of times.
    for _ in range(3):
        # Check that the HTTP server is reachable.  We suppress output
        # because this is just a health probe.
        hit = run("curl -sf http://127.0.0.1:8080", capture_output=True)
        if hit.returncode == 0:
            break
        subprocess.Popen("sleep 2".split()).wait()
    else:
        raise AssertionError("HTTP server did not start")

    # 3. Run the smoke test script.
    smoke = run("./scripts/check_deploy.sh", capture_output=True)
    assert smoke.returncode == 0, f"smoke test failed: {smoke.stdout}\n{smoke.stderr}"

