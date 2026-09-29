"""S3 vault helper for provenance evidence object locking (PRV-08).

PRV-08 upload is gated until PRV-01..07 are merged; currently provides the status
helper only. Because upload is not implemented yet, s3_status() must never report "ok".
"""

from __future__ import annotations

import os
from typing import Literal


def s3_status() -> Literal["disabled", "down"]:
    """Return status of S3 vault storage: "disabled" if SB_S3_BUCKET is empty/unset, else "down".

    Upload is not implemented yet, so this function never reports "ok".
    """
    bucket = os.getenv("SB_S3_BUCKET", "").strip()
    if not bucket:
        return "disabled"
    return "down"
