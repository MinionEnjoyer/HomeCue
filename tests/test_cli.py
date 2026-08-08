import subprocess
import sys


def test_help_does_not_require_windows_corsair_sdk() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "homecue", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Bridge Corsair iCUE RGB lighting" in result.stdout
    assert "--no-pause" not in result.stdout
