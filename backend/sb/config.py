import os

# UPSTREAM_ORIGIN selects the public CampusCart deployment. SB_ORIGIN_URL remains
# an explicit local-origin override for the existing ExampleCorp demo and tests.
SB_ORIGIN_URL = (
    os.getenv("UPSTREAM_ORIGIN")
    or os.getenv("SB_ORIGIN_URL")
    or "https://campuscart-c73de.web.app"
)

# Layer 1 Configuration
L1_RATE_WINDOW_SECS = int(os.getenv("L1_RATE_WINDOW_SECS", "10"))
L1_RATE_SOFT = int(os.getenv("L1_RATE_SOFT", "20"))
L1_RATE_HARD = int(os.getenv("L1_RATE_HARD", "40"))
L1_REPEAT_THROTTLE_WINDOW_SECS = int(os.getenv("L1_REPEAT_THROTTLE_WINDOW_SECS", "30"))
L1_REPEAT_THROTTLE_LIMIT = int(os.getenv("L1_REPEAT_THROTTLE_LIMIT", "3"))
L1_BLOCK_TTL_SECS = int(os.getenv("L1_BLOCK_TTL_SECS", "300"))

# Layer 2 Configuration
# PoW: sha256(challenge_id + ":" + nonce) with 14 leading zero bits.
# 14 zero bits  ≡  int(hexdigest[:4], 16) < 4  (2^14 = 16384 = 0x4000).
L2_POW_ZERO_BITS = int(os.getenv("L2_POW_ZERO_BITS", "14"))
L2_CHALLENGE_TTL_SECS = int(os.getenv("L2_CHALLENGE_TTL_SECS", "60"))
L2_CLEARANCE_TTL_SECS = int(os.getenv("L2_CLEARANCE_TTL_SECS", "900"))   # 15 min
L2_NO_JS_WINDOW_SECS = int(os.getenv("L2_NO_JS_WINDOW_SECS", "60"))
L2_NO_JS_LIMIT = int(os.getenv("L2_NO_JS_LIMIT", "3"))

# HMAC secret for sb_clear cookie; override in production via env var.
SB_SECRET = os.getenv("SB_SECRET", "dev-secret-change-in-production")
