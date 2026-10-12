// blazeAhead site settings: links, team and version. (The tour's words live in tour-content.js.)
// Paste full links that start with https://. Leave a link empty ('') and the page shows "Link coming soon".
window.BLAZEAHEAD_SITE = {
  teamName: '',                   // shown in the footer and on the Help page, e.g. 'the Developer Tools team'
  gitlabProjectUrl: '',           // e.g. 'https://gitlab.example.com/devtools/blazeahead'
  vsixFileName: 'blazeAhead.vsix',
  downloadLink: 'release-page',   // 'release-page' opens the newest release; 'direct' downloads the .vsix (see README)
  downloadUrl: '',                // optional: a full link to the .vsix somewhere else (e.g. Artifactory); overrides the two above
  version: '',                    // shown under the Download button, e.g. '1.4.0'
  releaseDate: '',                // e.g. '25 Sep 2026'
  links: {
    docs: '',                     // the usage docs (Confluence)
    issues: '',                   // where people report problems (your Jira project or service desk)
  },
};
