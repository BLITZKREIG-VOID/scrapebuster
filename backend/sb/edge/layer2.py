import hashlib
import time
import uuid
from dataclasses import dataclass

from fastapi import Response

from .session import Session

# Configuration: difficulty level
POW_DIFFICULTY = "000"
CHALLENGE_TTL_SECS = 300

@dataclass
class Challenge:
    challenge_id: str
    session_id: str
    nonce: str
    expiry: float
    used: bool = False

class ChallengeStore:
    def __init__(self):
        self._challenges: dict[str, Challenge] = {}

    def create(self, session: Session) -> Challenge:
        cid = f"ch-{uuid.uuid4().hex}"
        nonce = uuid.uuid4().hex
        expiry = time.time() + CHALLENGE_TTL_SECS
        c = Challenge(cid, session.session_id, nonce, expiry)
        self._challenges[cid] = c
        return c

    def get(self, challenge_id: str) -> Challenge | None:
        return self._challenges.get(challenge_id)
        
    def reset(self):
        self._challenges.clear()

store = ChallengeStore()

def generate_challenge_response(session: Session) -> Response:
    """
    Generates a Layer 2 challenge (HTML + JS) for the given session.
    """
    challenge = store.create(session)
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Security Check</title>
    <style>
        body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #f0f2f5; margin: 0; }}
        .box {{ background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 400px; width: 100%; }}
        .loader {{ border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 2s linear infinite; margin: 1rem auto; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="box">
        <h2>Security Check</h2>
        <p>Please wait while we verify your browser...</p>
        <div class="loader"></div>
        <div id="status" style="color: #666; font-size: 0.9rem;">Initializing...</div>
    </div>
    <script>
        const CHALLENGE_ID = "{challenge.challenge_id}";
        const NONCE = "{challenge.nonce}";
        const DIFFICULTY = "{POW_DIFFICULTY}";
    </script>
    <script src="/_sb/static/challenge.js"></script>
</body>
</html>"""
    # We return 403 status code for the challenge page so automated tools don't parse it as a 200 OK success
    # But browsers will execute the JS and refresh. Actually, Cloudflare returns 403 or 202. We can use 403.
    return Response(content=html, media_type="text/html", status_code=403)

def verify(challenge_id: str, solution: str, session: Session) -> bool:
    """
    Verifies a PoW solution for a given challenge.
    """
    c = store.get(challenge_id)
    if not c:
        return False
        
    if c.session_id != session.session_id:
        return False
        
    if time.time() > c.expiry:
        return False
        
    if c.used:
        return False
        
    c.used = True
    
    if not solution:
        return False
        
    # Check PoW: SHA256(nonce + solution) starts with DIFFICULTY
    text = c.nonce + solution
    hash_val = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if not hash_val.startswith(POW_DIFFICULTY):
        return False
        
    return True
