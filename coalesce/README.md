# Coalesce website

The project home for Coalesce, the Excel add-in. It has two pages:
- **Home:** download, install, docs, releases, access.
- **Help:** service desk, tutorial, SOP.

Both open with an interactive 3D figure made of many small people.

The site is plain HTML, CSS and JavaScript. GitLab Pages publishes the `public/` folder exactly as it is: there is no build step and no server code.

## Install it in your GitLab project

The zip holds a `coalesce-site/` folder, and this guide is inside it as `SITE-README.md`. Copy only the pieces below into your project's repository, so nothing of yours gets overwritten:

1. **The website:** copy `public/` into your repository. If you already have a `public/` folder, copy these files into it and keep anything else you host there.
2. **The Pages job:**
   - No `.gitlab-ci.yml` yet? Copy ours.
   - You have one, but it has no `pages` job? Paste our `pages` job into it and leave your other jobs alone.
   - You already have a `pages` job that publishes `public/`? Change nothing.
3. **Optional extras:** `tools/` (release script, local preview, checks) and `blender/` (the 3D sources). If those folder names are already taken in your project, put them under a folder such as `site-tools/`.
4. Fill in `public/site-config.js` (see the next section). Then commit and push to your default branch. The **pages** job publishes the site in a minute or two, and **Deploy → Pages** shows its address.

### Updating the site later

Copy the new `public/` over the old one, but keep your `site-config.js`. If you overwrite it, your links go back to "Link coming soon".

## The settings file

Every link, your team name and the version shown on the page live in `public/site-config.js`. Paste full links that start with `https://`. If a setting is left empty, the page shows "Link coming soon" instead of a broken link.

| Setting | What it's for |
|---|---|
| `teamName` | Shown in the footer and on the Help page |
| `gitlabProjectUrl` | Your project's address, for example `https://gitlab.example.com/ops/coalesce`. The Releases, Download and GitLab project links are built from it |
| `xlamFileName` | The add-in's file name (normally `Coalesce.xlam`) |
| `downloadLink` | `'release-page'` (the default): Download opens the newest release. `'direct'`: Download fetches the newest `.xlam` itself (see the next section) |
| `version`, `releaseDate` | Shown under the Download button; update them with each release |
| `links.docs` | The usage docs / SOP |
| `links.tutorial` | The interactive tutorial |
| `links.serviceDesk` | Your Jira service desk portal (also used for "Report an issue") |
| `links.access` | How to request access |

## Publishing a release

GitLab can give a release file a permanent "always the newest" address. It only does that when the file is attached through its API, and `tools/publish-release.ps1` handles that for you from Windows PowerShell:

```powershell
$env:GITLAB_TOKEN = '<a personal access token with the api scope>'
powershell -ExecutionPolicy Bypass -File .\tools\publish-release.ps1 -GitLabUrl https://gitlab.example.com -Project ops/coalesce -Version 2.4.0 -File .\Coalesce.xlam
```

The script:
- uploads the file to the project's package registry;
- creates release `v2.4.0` from `main` (change it with `-Ref`, add release notes with `-Notes "…"`);
- with `-DryRun`, shows what it would send without sending anything.

After your first release made this way, set `downloadLink: 'direct'` in `site-config.js`. From then on, the Download button fetches the newest file. With each release, also update `version` and `releaseDate` there.

It needs GitLab 15.9 or newer, because older versions ignore the direct asset path and 'direct' downloads would fail. On older GitLab, keep `downloadLink: 'release-page'`. You also need a personal access token with the `api` scope. To create one, go to your avatar → **Edit profile** → **Access tokens**.

## Preview on your PC

With Python installed, run this from the unzipped folder:

```powershell
python tools/serve.py
```

Then open <http://127.0.0.1:8000/>. Double-clicking `index.html` won't show the 3D figure, because browsers block 3D files opened straight from disk.

## When the page shows a picture instead of the 3D figure

The page shows a still image instead of the live figure in these cases:
- on phones and tablets;
- when Windows' **Show animations** setting is off;
- on PCs without 3D graphics (some virtual desktops);
- on PCs too slow to animate it smoothly.

Everything else on the page works the same. On other PCs, a **Pause motion** button stops the animation.

## Changing the look

- **Shapes and still images:** the small person, the magnifying glass and the still images come from `blender/build_coalesce.py` (Blender 5.2 LTS).
- **Positions:** where the people stand comes from `blender/coalesce_layout.py`.
- **Colors and wording:** `public/css/site.css` and the two HTML files.

After editing either Blender file, rebuild:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_coalesce.py -- --stills
```

That rewrites `public/assets/` and `blender/coalesce.blend` (open the `.blend` for hand edits).

## Checking a change

`tools/verify.py` takes screenshots of every state into `verify-output/` and checks the size and speed budgets. It needs the dev tools first:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tools/verify.py
```

## Licenses

The site includes Three.js (MIT, `public/vendor/three/LICENSE`) and the Instrument Serif and Instrument Sans fonts (SIL Open Font License, `public/fonts/OFL.txt`), each with its license.
