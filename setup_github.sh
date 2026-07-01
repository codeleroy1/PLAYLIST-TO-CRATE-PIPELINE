#!/usr/bin/env bash
# setup_github.sh — initialize git (if needed) and publish this repo to GitHub.
set -euo pipefail

cd "$(dirname "$0")"

echo "== DJ Leroy Pipeline — GitHub setup =="
echo

# 1. Init git if this somehow isn't already a repo
if [ ! -d .git ]; then
    echo "No git repo found here — initializing one."
    git init -q
else
    echo "Existing git repo found."
fi

# 2. Optionally set commit author
read -r -p "Set commit author name/email for this repo? [y/N] " set_author
if [[ "$set_author" =~ ^[Yy]$ ]]; then
    read -r -p "  Name: " author_name
    read -r -p "  Email: " author_email
    git config user.name "$author_name"
    git config user.email "$author_email"
    echo "  Author set."
fi

# 3. Stage + commit if there's anything to commit
if ! git diff --cached --quiet 2>/dev/null || ! git diff --quiet 2>/dev/null || [ -z "$(git log -1 2>/dev/null || true)" ]; then
    git add -A
    if ! git diff --cached --quiet; then
        read -r -p "Commit message [Initial commit: DJ Leroy pipeline]: " commit_msg
        commit_msg="${commit_msg:-Initial commit: DJ Leroy pipeline}"
        git commit -q -m "$commit_msg"
        echo "Committed."
    else
        echo "Nothing new to commit."
    fi
fi

# 4. Ask for repo details
echo
read -r -p "GitHub username: " gh_user
read -r -p "Repo name [dj-leroy-pipeline]: " repo_name
repo_name="${repo_name:-dj-leroy-pipeline}"
read -r -p "Visibility (public/private) [public]: " visibility
visibility="${visibility:-public}"

# 5. Prefer GitHub CLI if available
if command -v gh >/dev/null 2>&1; then
    echo
    echo "GitHub CLI found — creating and pushing repo..."
    gh repo create "$repo_name" "--$visibility" --source=. --remote=origin --push
    echo
    echo "Done. Repo: https://github.com/$gh_user/$repo_name"
else
    echo
    echo "GitHub CLI ('gh') not found. Setting up a manual remote instead."
    echo "Create an EMPTY repo first at: https://github.com/new"
    echo "  (name it '$repo_name', do NOT initialize with README/license — this repo already has both)"
    read -r -p "Press Enter once you've created it on github.com..." _

    remote_url="https://github.com/$gh_user/$repo_name.git"
    if git remote get-url origin >/dev/null 2>&1; then
        git remote set-url origin "$remote_url"
    else
        git remote add origin "$remote_url"
    fi
    git branch -M main

    echo
    echo "Remote set to: $remote_url"
    echo "Run this to finish publishing:"
    echo
    echo "    git push -u origin main"
    echo
    echo "(You'll be prompted to authenticate — browser login or a personal access token.)"
fi
