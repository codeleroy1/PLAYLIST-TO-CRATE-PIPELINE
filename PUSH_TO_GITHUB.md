# Publishing to GitHub

This repo is already git-initialized with an initial commit. You just need to
push it somewhere. Pick whichever path fits how you work.

## Pre-publish checklist

Before pushing, confirm:

- [ ] `git log --stat` shows only the files listed in this repo's README — no personal Exportify CSVs, no real `_config.json`/`_matched.json`/`_youtube.json` session files, no actual `.mp3`/`.crate` files
- [ ] `examples/sample_playlist_export.csv` contains only fictional artist/track names (it does — check for yourself, it's five made-up tracks)
- [ ] No hardcoded personal paths, API keys, or credentials appear anywhere (`grep -r "api_key\|password\|token" .` turns up nothing)
- [ ] `.gitignore` is in place (it already excludes audio files, crate output, and session data by pattern, as a safety net for future commits)

## Option A — GitHub CLI (fastest)

```bash
gh repo create dj-leroy-pipeline --public --source=. --remote=origin --push
```
Use `--private` instead of `--public` if you'd rather not make it public yet.

## Option B — Manual git

```bash
git remote add origin https://github.com/YOUR_USERNAME/dj-leroy-pipeline.git
git branch -M main
git push -u origin main
```

(Create the empty repo first at https://github.com/new — don't initialize it
with a README/license there, since this repo already has both.)

## Option C — No terminal, web upload

1. Go to https://github.com/new, name it (e.g. `dj-leroy-pipeline`), leave it
   empty (no README/license/gitignore), click **Create repository**.
2. On the new repo's page, click **uploading an existing file**.
3. Unzip the archive you downloaded locally, then drag the *contents* of the
   `dj-leroy-pipeline/` folder into the upload area (not the zip itself).
4. Note: this method does **not** carry over git history/commits — it creates
   one new commit from whatever you drag in. If you want the original commit
   history, use Option A or B instead.

## Suggested repo description & topics

**Description:**
> Spotify playlist → local DJ library pipeline: match, download, tag, and build a crate for Serato/Rekordbox/Traktor/Engine DJ.

**Topics:**
`dj-tools` `serato` `rekordbox` `traktor` `spotify` `yt-dlp` `id3-tags` `mutagen` `music-library` `python`

## Your one remaining manual step

Everything above through "push" requires your own GitHub authentication —
that's the one step nobody else can do for you. Run whichever of Option A or
B fits your setup, authenticate when prompted (browser login for `gh`, or a
personal access token / SSH key for plain `git push`), and the repo is live.
