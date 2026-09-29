import fnmatch
import os
import subprocess
import sys


def get_current_user():
    user = os.environ.get("GITHUB_ACTOR")
    if not user:
        try:
            user = subprocess.check_output(["git", "config", "user.name"], text=True).strip()
        except subprocess.CalledProcessError:
            pass
    if not user:
        print("WARNING: Could not determine current user (no GITHUB_ACTOR or git config user.name).")
        return None
    # Normalize user (in case it has spaces or different casing locally)
    # E.g. "Anirudh Gupta" -> "anirudh"
    user_lower = user.lower()
    if "anirudh" in user_lower or "anigupta" in user_lower:
        return "@anirudh"
    if "hardik" in user_lower:
        return "@hardik"
    if "arnav" in user_lower:
        return "@arnav"
    if "harsh" in user_lower:
        return "@harsh"
    
    # Fallback if no hardcoded mapping matches, assume they use their handle directly
    return f"@{user_lower.split()[0]}"

def get_changed_files():
    files = set()
    try:
        # Check diff against origin/main if it exists
        out = subprocess.check_output(["git", "diff", "--name-only", "origin/main...HEAD"], text=True, stderr=subprocess.DEVNULL)
        files.update(out.strip().splitlines())
    except subprocess.CalledProcessError:
        pass
        
    try:
        # Check staged and unstaged files
        staged = subprocess.check_output(["git", "diff", "--name-only", "--cached"], text=True)
        files.update(staged.strip().splitlines())
        unstaged = subprocess.check_output(["git", "diff", "--name-only"], text=True)
        files.update(unstaged.strip().splitlines())
    except subprocess.CalledProcessError:
        pass
        
    return {f for f in files if f.strip() and os.path.exists(f)}

def parse_codeowners(codeowners_path):
    rules = []
    with open(codeowners_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                pattern = parts[0]
                owners = parts[1:]
                rules.append((pattern, owners))
    return rules

def get_file_owners(filepath, rules):
    # Normalize filepath to use forward slashes
    filepath = filepath.replace("\\", "/")
    
    file_owners = []
    # Last matching rule wins
    for pattern, owners in rules:
        # Handle CODEOWNERS patterns
        # * -> matches everything
        # /dir/ -> matches dir at root
        # dir/ -> matches dir anywhere
        match = False
        if pattern == "*":
            match = True
        elif pattern.startswith("/"):
            # absolute path from root
            pat = pattern[1:]
            if pat.endswith("/"):
                if filepath.startswith(pat):
                    match = True
            else:
                if filepath == pat or fnmatch.fnmatch(filepath, pat):
                    match = True
        else:
            if pattern.endswith("/"):
                if filepath.startswith(pattern) or f"/{pattern}" in filepath:
                    match = True
            else:
                if filepath == pattern or fnmatch.fnmatch(filepath, pattern):
                    match = True
                    
        if match:
            file_owners = owners
            
    return file_owners

def check_ownership():
    codeowners_path = os.path.join(os.path.dirname(__file__), "..", ".github", "CODEOWNERS")
    if not os.path.exists(codeowners_path):
        print("ERROR: CODEOWNERS file not found.")
        return 1
        
    user = get_current_user()
    if not user:
        # Cannot enforce
        return 0

    rules = parse_codeowners(codeowners_path)
    changed_files = get_changed_files()
    
    if not changed_files:
        print(f"Ownership check passed (no files changed). User: {user}")
        return 0

    violations = []
    
    for f in changed_files:
        owners = get_file_owners(f, rules)
        # If the file has no owners or the user is one of the owners, it's fine.
        if owners and user not in [o.lower() for o in owners]:
            violations.append((f, owners))
            
    if violations:
        print(f"WARNING: User {user} modified files outside their owned paths:")
        for f, owners in violations:
            print(f"  - {f} (owned by {', '.join(owners)})")
        print("\nPlease ensure you have approval from the owners before merging.")
        # The Master Plan says "warning in PR". We can return 0 so it doesn't fail the build outright,
        # or we can return 1 if we want it to block `make check`.
        # "do not silently claim success when ownership cannot be evaluated" -> we already warn if user is missing.
        # Returning 0 but printing a bold warning fulfills "warning in PR", but if we want to enforce it, returning 1 is better.
        # I'll return 0 so `make check` doesn't permanently block cross-team collaboration without override, 
        # but the warning will be visible in the PR.
        # Wait, the prompt says "produce a warning/report for ownership boundary violations".
        return 0
        
    print(f"Ownership check passed for {len(changed_files)} changed files. User: {user}")
    return 0

if __name__ == "__main__":
    sys.exit(check_ownership())
