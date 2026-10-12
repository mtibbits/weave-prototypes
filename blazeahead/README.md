# blazeAhead website

The project home for blazeAhead, the VS Code extension for Claude Code on our network. It has three pages:
- **Home:** download, install steps, and a live 3D trailhead: a log signpost and a torch at the mouth of a forest path.
- **Tour:** a walk down the torch-lit path with four stops, one per feature. The stops are the continuity proxy (a stream), environment scaffolding (a base camp), the knowledge base (a map board) and the In Flight queue (a launch clearing). Signposts at the left and right edges lead back and on.
- **Help:** a trail junction whose signpost points to Issues, Docs and the Tour.

The site is plain HTML, CSS and JavaScript. GitLab Pages publishes the `public/` folder exactly as it is: there is no build step and no server code.

## Install it in your GitLab project

The zip holds a `blazeahead-site/` folder, and this guide is inside it as `SITE-README.md`. Copy only the pieces below into your project's repository, so nothing of yours gets overwritten:

1. **The website:** copy `public/` into your repository. If you already have a `public/` folder (today's slide page, say), copy these files into it; remove the old page when you're ready.
2. **The Pages job:**
   - No `.gitlab-ci.yml` yet? Copy ours.
   - You have one, but it has no `pages` job? Paste our `pages` job into it and leave your other jobs alone.
   - You already have a `pages` job that publishes `public/`? Change nothing.
3. **Optional extras:** `tools/` (release script, local preview, checks) and `blender/` (the 3D sources). If those folder names are already taken in your project, put them under a folder such as `site-tools/`.
4. Fill in `public/site-config.js` and read through `public/tour-content.js` (see the next section). Then commit and push to your default branch. The **pages** job publishes the site in a minute or two, and **Deploy → Pages** shows its address.

### Updating the site later

Copy the new `public/` over the old one, but keep your `site-config.js` and `tour-content.js`. If you overwrite them, your links go back to "Link coming soon" and the tour goes back to the draft copy.

## The settings files

**`public/site-config.js`** holds every link, your team name and the version shown on the page. Paste full links that start with `https://`. If a setting is left empty, the page shows "Link coming soon" instead of a broken link.

| Setting | What it's for |
|---|---|
| `teamName` | Shown in the footer and on the Help page |
| `gitlabProjectUrl` | Your project's address, for example `https://gitlab.example.com/devtools/blazeahead`. The Releases, Download and GitLab project links are built from it |
| `vsixFileName` | The extension's file name (normally `blazeAhead.vsix`) |
| `downloadLink` | `'release-page'` (the default): Download opens the newest release. `'direct'`: Download fetches the newest `.vsix` itself (see [Publishing a release](#publishing-a-release)) |
| `downloadUrl` | Optional. A full link to the `.vsix` somewhere else (Artifactory, a file share on the web). When set, it wins over the two settings above |
| `version`, `releaseDate` | Shown under the Download button; update them with each release |
| `links.docs` | The usage docs |
| `links.issues` | Where people report problems (your Jira project or service desk); used by "Report an issue" and the Help page |

**`public/tour-content.js`** holds the tour's words: the word on each signpost (`sign`), each stop's title, paragraphs and bullet points, the knowledge-base trail map, the three arms of the Help signpost, and what each rock in the stream stands for.
- **The copy shipped here is a draft**, written from one-line descriptions of each feature. Replace it with your own.
- The trail has exactly four stop scenes, in a fixed order: stream, camp, map board, launch clearing. Stops map to them in that order; extra stops are ignored.
- Anything you leave out falls back to the draft text in `js/content.js`, so a mistake in this file can't break the tour.
- Keep `sign` words short: they have to fit on an 18-inch board.
- **The trail map** is the `map` in the knowledge stop: trails from the centre, each with its destinations, and a destination can lead on to more (`next`). It holds up to 5 trails, 5 destinations on a trail, 2 onward stops per destination, and 25 stops in all. A `url` that starts with `https://` or `http://` makes a name a link on the card and on the unfolded map. The map lays itself out, and a change shows up everywhere (the 3D kiosk, the still image and the unfolded map) as soon as you publish. No re-render is needed. If a very full map can't fit every name cleanly, it still draws, and the browser console says so.
- The live 3D scene draws the signpost words from this file, so a new word appears as soon as you publish. The still images (used when 3D can't run) have the words painted in. After changing a `sign` word, re-render the stills (see [Rebuilding the 3D world](#rebuilding-the-3d-world)); the build reads the words from this same file.

## Installing the extension (what the Home page tells people)

1. Download `blazeAhead.vsix`.
2. In VS Code, open the Extensions view (**Ctrl+Shift+X**), click the **…** menu at its top and choose **Install from VSIX…**, then pick the file. From a terminal: `code --install-extension blazeAhead.vsix`.
3. Reload VS Code when it asks. The flame appears in the activity bar.

## Publishing a release

GitLab can give a release file a permanent "always the newest" address. It only does that when the file is attached through its API, and `tools/publish-release.ps1` handles that for you from Windows PowerShell:

```powershell
$env:GITLAB_TOKEN = '<a personal access token with the api scope>'
powershell -ExecutionPolicy Bypass -File .\tools\publish-release.ps1 -GitLabUrl https://gitlab.example.com -Project devtools/blazeahead -Version 1.4.0 -File .\blazeAhead.vsix
```

The script:
- uploads the file to the project's package registry;
- creates release `v1.4.0` from `main` (change it with `-Ref`, add release notes with `-Notes "…"`);
- with `-DryRun`, shows what it would send without sending anything.

After your first release made this way, set `downloadLink: 'direct'` in `site-config.js`. From then on, the Download button fetches the newest file. With each release, also update `version` and `releaseDate` there.

It needs GitLab 15.9 or newer, because older versions ignore the direct asset path and 'direct' downloads would fail. On older GitLab, keep `downloadLink: 'release-page'`. You also need a personal access token with the `api` scope. To create one, go to your avatar → **Edit profile** → **Access tokens**.

## Preview on your PC

With Python installed, run this from the unzipped folder:

```powershell
python tools/serve.py
```

Then open <http://127.0.0.1:8000/>. Double-clicking `index.html` won't show the 3D scene, because browsers block 3D files opened straight from disk.

## When the page shows a picture instead of the 3D scene

The pages show still images instead of the live scene in these cases:
- when Windows' **Show animations** setting is off (the tour then switches between stops without walking);
- on PCs without 3D graphics (some virtual desktops);
- on PCs too slow to animate it smoothly (checked during the first two seconds);
- on touch-only devices.

Everything else works the same, including the tour. On other PCs, a **Pause motion** button stops the idle animation.

The tour never waits long for the 3D scene (about 1.9 MB). A link to a stop opens that stop's picture and words at once. A first visit waits a few seconds at the trailhead for the walk, then sets off on pictures. Either way, the 3D scene takes over at the current stop once it has loaded.

## Rebuilding the 3D world

Everything in the scene comes from two Blender scripts (Blender 5.2 LTS):
- `blender/blazeahead_layout.py` is the world itself: the path, the stops, where every tree and fern stands, the camera views and walks, and the baked light.
- `blender/build_blazeahead.py` turns that into `public/assets/` (the GLB and JSON) and, with `--stills`, the six still images.

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_blazeahead.py
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python-exit-code 1 --python blender/build_blazeahead.py -- --stills
```

The first command takes about a minute. The second also renders the stills with Cycles, which takes about 40 minutes on a laptop CPU; add `--only knowledge,junction` to redo just some of them. The stills paint the signpost words from `public/tour-content.js`; the build prints them on a `SIGNS` line so you can check them before the render finishes. Open `blender/blazeahead.blend` to look at the pieces.

Colors and wording of the pages are in `public/css/site.css` and the three HTML files.

## Checking a change

The tests and `tools/verify.py` need the dev tools first:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m pytest                    # the fast suite (about two minutes)
.venv\Scripts\python -m pytest -m slow            # runs the Blender build
.venv\Scripts\python tools\verify.py              # screenshots of every page and stop, plus the speed budgets
```

`verify.py` writes its screenshots to `verify-output/` and fails if a page is too slow or too heavy.

## Decisions waiting for you

These were built with a sensible default because nobody was around to ask. Each one is quick to change.

1. **Where the download lives.** Assumed: a `.vsix` on GitLab releases, published with `tools/publish-release.ps1`. If it lives in Artifactory instead, set `downloadUrl` in `site-config.js` to its address.
2. **The look.** Assumed free rein: a night-forest palette (ink, torch amber, crystal blue) with the Fraunces and Figtree fonts. If the site must match another style, the colors are the variables at the top of `css/site.css`.
3. **The Help signpost.** Assumed its three arms are Issues, Docs and Tour (`help.signs` in `tour-content.js`).
4. **Today's slide page.** Assumed it is retired and its content moves into the four stops.
5. **The tour's words.** Draft copy; the knowledge-base cards are placeholders.
6. **The flame.** It is our own design, a flame with a blue crystal, inspired by the coworker's icon but not copied from it. A picture of the real icon would let the 3D flame and the favicon match it.
7. **The quote.** "Do not go where the path may lead…" is usually credited to Emerson, but it isn't in his writings; the earliest known version is Muriel Strode's 1903 poem "Wind-Wafted Wild Flowers". The site doesn't quote it; the extension's sidebar does.

## Known limits

The final review found these small things and left them for later:
- **A tour cut to fewer than four stops.** In the 3D scene, the last stop's right-hand signpost still shows the next default word ("In Flight"), although its button says "Next: Download" and goes there.
- **Browser Back during a walk.** Pressing Back while the camera is walking can leave a repeated history entry, so a later Back press seems to do nothing.
- **Keyboard.** While the camera walks, the hidden card's ‹ › buttons can still take focus. After paging to the last knowledge-base card, focus goes back to the top of the page.
- **The skip link.** "Skip to the tour card" puts `#tour-card` in the address; reloading then starts the tour at the first stop.
- **The release script's built-in help.** Its example shows a garbled file name; the example in [Publishing a release](#publishing-a-release) is right.

## Licenses

The site includes Three.js (MIT, `public/vendor/three/LICENSE`) and the Fraunces and Figtree fonts (SIL Open Font License, `public/fonts/OFL.txt`), each with its license. The 3D world, the flame and the signposts are our own work.
