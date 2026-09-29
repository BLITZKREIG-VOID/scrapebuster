async function sha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

async function solveChallenge() {
    let answer = 0;
    const statusEl = document.getElementById('status');
    statusEl.innerText = "Computing verification...";
    
    while (true) {
        let hash = await sha256(NONCE + answer.toString());
        if (hash.startsWith(DIFFICULTY)) {
            return answer.toString();
        }
        answer++;
        
        // Yield to the event loop every 1000 iterations so the UI doesn't freeze
        if (answer % 1000 === 0) {
            await new Promise(r => setTimeout(r, 0));
        }
    }
}

async function submitSolution(solution) {
    const statusEl = document.getElementById('status');
    statusEl.innerText = "Submitting...";
    
    try {
        const res = await fetch('/_sb/challenge/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                challenge_id: CHALLENGE_ID,
                solution: solution,
                signals: {
                    userAgent: navigator.userAgent,
                    language: navigator.language
                }
            })
        });
        
        if (res.ok) {
            statusEl.innerText = "Success! Redirecting...";
            window.location.reload();
        } else {
            statusEl.innerText = "Verification failed. Please refresh the page.";
        }
    } catch (e) {
        statusEl.innerText = "Network error during verification.";
    }
}

// Start immediately
if (window.crypto && window.crypto.subtle) {
    solveChallenge().then(submitSolution).catch(err => {
        document.getElementById('status').innerText = "Error during verification: " + err.message;
    });
} else {
    document.getElementById('status').innerText = "Your browser does not support the required cryptography features.";
}
