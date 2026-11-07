"""The documented expiry command must dispatch without touching remote state."""

import subprocess
from unittest.mock import patch

from deployment import validate


def test_verify_expiry_dispatches_existing_runner():
    with patch("subprocess.run") as run, patch.object(validate, "RemoteLab") as lab:
        validate.main(["verify-expiry"])
    lab.assert_not_called()
    run.assert_called_once_with(
        [validate.sys.executable, str(validate.ROOT / "deployment/expiry.py")],
        check=True,
    )


def test_verify_expiry_preserves_failure():
    with patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "expiry")
    ):
        import pytest

        with pytest.raises(subprocess.CalledProcessError):
            validate.main(["verify-expiry"])
