/**
 * ScapeBusters Layer 2 — challenge.js
 * ====================================
 * Pure-JS SHA-256 (no SubtleCrypto), 8 signal collection, 14-bit PoW,
 * POSTs to /_sb/verify.
 *
 * Injected globals (from interstitial HTML):
 *   SB_CHALLENGE_ID  — server-issued challenge UUID
 *   SB_RETURN_TO     — URL to navigate to after pass
 *   SB_LOAD_TIME     — Date.now() at page load (ms)
 *   SB_POW_BITS      — number of leading zero bits required (14)
 */

/* -------------------------------------------------------------------------
 * Minimal pure-JS SHA-256 (RFC 6234 / FIPS 180-4)
 * No SubtleCrypto — works in headless browsers that disable WebCrypto.
 * Based on the public-domain implementation by Chris Veness (MIT).
 * ------------------------------------------------------------------------- */
(function (global) {
    'use strict';
    var K = [
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,
        0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
        0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,
        0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,
        0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
        0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,
        0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,
        0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
        0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
    ];

    function sha256hex(msg) {
        var bytes = [];
        for (var i = 0; i < msg.length; i++) {
            var c = msg.charCodeAt(i);
            if (c < 0x80) { bytes.push(c); }
            else if (c < 0x800) {
                bytes.push(0xc0 | (c >> 6));
                bytes.push(0x80 | (c & 0x3f));
            } else {
                bytes.push(0xe0 | (c >> 12));
                bytes.push(0x80 | ((c >> 6) & 0x3f));
                bytes.push(0x80 | (c & 0x3f));
            }
        }
        var l = bytes.length * 8;
        bytes.push(0x80);
        while (bytes.length % 64 !== 56) bytes.push(0);
        // 64-bit big-endian length
        for (var s = 56; s >= 0; s -= 8) bytes.push((l / Math.pow(2, s)) & 0xff);

        var H = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,
                 0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];

        for (var b = 0; b < bytes.length; b += 64) {
            var W = [];
            for (var t = 0; t < 16; t++)
                W[t] = (bytes[b+t*4]<<24)|(bytes[b+t*4+1]<<16)|(bytes[b+t*4+2]<<8)|bytes[b+t*4+3];
            for (t = 16; t < 64; t++) {
                var s0 = ror(W[t-15],7) ^ ror(W[t-15],18) ^ (W[t-15]>>>3);
                var s1 = ror(W[t-2],17) ^ ror(W[t-2],19)  ^ (W[t-2]>>>10);
                W[t] = (W[t-16]+s0+W[t-7]+s1) | 0;
            }
            var a=H[0],b_=H[1],c=H[2],d=H[3],e=H[4],f=H[5],g=H[6],h=H[7];
            for (t = 0; t < 64; t++) {
                var S1 = ror(e,6)^ror(e,11)^ror(e,25);
                var ch = (e&f)^(~e&g);
                var tmp1 = (h+S1+ch+K[t]+W[t]) | 0;
                var S0 = ror(a,2)^ror(a,13)^ror(a,22);
                var maj = (a&b_)^(a&c)^(b_&c);
                var tmp2 = (S0+maj) | 0;
                h=g; g=f; f=e; e=(d+tmp1)|0; d=c; c=b_; b_=a; a=(tmp1+tmp2)|0;
            }
            H[0]=(H[0]+a)|0; H[1]=(H[1]+b_)|0; H[2]=(H[2]+c)|0; H[3]=(H[3]+d)|0;
            H[4]=(H[4]+e)|0; H[5]=(H[5]+f)|0; H[6]=(H[6]+g)|0; H[7]=(H[7]+h)|0;
        }
        var hex = '';
        for (var i2 = 0; i2 < 8; i2++)
            hex += ('00000000' + (H[i2] >>> 0).toString(16)).slice(-8);
        return hex;
    }

    function ror(n, s) { return (n >>> s) | (n << (32-s)); }

    global.SB_SHA256 = sha256hex;
})(typeof window !== 'undefined' ? window : this);


/* -------------------------------------------------------------------------
 * Signal collection  (§5 — 8 signals)
 * ------------------------------------------------------------------------- */
var _sbSignals = {
    webdriver:     false,
    headlessChrome:false,
    navigatorUA:   '',
    outerWidth:    0,
    outerHeight:   0,
    softwareGL:    false,
    languages:     [],
    mousemove:     0,
    scroll:        0,
    keydown:       0
};

(function collectSignals() {
    try { _sbSignals.webdriver = !!navigator.webdriver; } catch(e) {}
    try { _sbSignals.headlessChrome = /HeadlessChrome/i.test(navigator.userAgent); } catch(e) {}
    try { _sbSignals.navigatorUA = navigator.userAgent; } catch(e) {}
    try { _sbSignals.outerWidth  = window.outerWidth; }  catch(e) {}
    try { _sbSignals.outerHeight = window.outerHeight; } catch(e) {}
    try {
        var canvas = document.createElement('canvas');
        var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            var dbgInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (dbgInfo) {
                var renderer = gl.getParameter(dbgInfo.UNMASKED_RENDERER_WEBGL) || '';
                _sbSignals.softwareGL = /SwiftShader|llvmpipe/i.test(renderer);
            }
        }
    } catch(e) {}
    try {
        var langs = navigator.languages;
        _sbSignals.languages = (langs && langs.length) ? Array.from(langs) : [];
    } catch(e) { _sbSignals.languages = []; }

    // Interaction event counters (observed for 1500 ms before PoW starts)
    function inc(key) { return function() { _sbSignals[key]++; }; }
    window.addEventListener('mousemove', inc('mousemove'));
    window.addEventListener('scroll',    inc('scroll'));
    window.addEventListener('keydown',   inc('keydown'));
})();


/* -------------------------------------------------------------------------
 * Proof-of-Work solver (pure-JS SHA-256, 14 leading zero bits)
 * sha256(SB_CHALLENGE_ID + ":" + candidate)
 * 14 zero bits  ≡  parseInt(hex.slice(0,4), 16) < 4
 * ------------------------------------------------------------------------- */
function sbSolvePoW(callback) {
    var statusEl = document.getElementById('status');
    if (statusEl) statusEl.innerText = 'Verifying\u2026';
    var threshold = 1 << (16 - SB_POW_BITS);   // 4 when SB_POW_BITS=14
    var candidate = 0;

    function step() {
        var limit = candidate + 2000;   // process 2000 candidates then yield
        while (candidate < limit) {
            var input = SB_CHALLENGE_ID + ':' + candidate.toString();
            var h = SB_SHA256(input);
            if (parseInt(h.slice(0, 4), 16) < threshold) {
                callback(candidate.toString(), h);
                return;
            }
            candidate++;
        }
        setTimeout(step, 0);   // yield to event loop
    }
    setTimeout(step, 0);
}


/* -------------------------------------------------------------------------
 * Main flow: wait 1500 ms for interaction signals, then solve PoW + submit
 * ------------------------------------------------------------------------- */
function sbSubmit(nonce, hash) {
    var elapsed = Date.now() - SB_LOAD_TIME;
    var payload = {
        challenge_id: SB_CHALLENGE_ID,
        nonce: nonce,
        signals: {
            webdriver:      _sbSignals.webdriver,
            headlessChrome: _sbSignals.headlessChrome,
            navigatorUA:    _sbSignals.navigatorUA,
            outerWidth:     _sbSignals.outerWidth,
            outerHeight:    _sbSignals.outerHeight,
            softwareGL:     _sbSignals.softwareGL,
            languages:      _sbSignals.languages,
            mousemove:      _sbSignals.mousemove,
            scroll:         _sbSignals.scroll,
            keydown:        _sbSignals.keydown,
            elapsed_ms:     elapsed
        }
    };

    fetch('/_sb/verify', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(function(r) { return r.json().then(function(j) { return {ok: r.ok, body: j}; }); })
    .then(function(res) {
        if (res.ok) {
            // PASS or silent-TRAP both return result:"pass"
            window.location.href = SB_RETURN_TO || window.location.pathname;
        } else {
            var el = document.getElementById('status');
            if (el) el.innerText = 'Verification failed. Please refresh.';
        }
    })
    .catch(function() {
        var el = document.getElementById('status');
        if (el) el.innerText = 'Network error during verification.';
    });
}

// Wait 1500 ms for interaction window, then solve and submit
setTimeout(function() {
    sbSolvePoW(sbSubmit);
}, 1500);
