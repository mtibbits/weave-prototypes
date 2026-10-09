// Coalesce site settings: the only file you need to edit.
// Paste full links that start with https://. Leave a link empty ('') and the page shows "Link coming soon".
window.COALESCE_SITE = {
  teamName: '',                  // shown in the footer and on the Help page, e.g. 'the Manpower Systems team'
  gitlabProjectUrl: '',          // e.g. 'https://gitlab.example.com/ops/coalesce'
  xlamFileName: 'Coalesce.xlam',
  downloadLink: 'release-page',  // 'release-page' opens the newest release; 'direct' downloads the file (see README)
  version: '',                   // shown under the Download button, e.g. '2.4.0'
  releaseDate: '',               // e.g. '23 Sep 2026'
  links: {
    docs: '',                    // usage docs / SOP
    tutorial: '',                // the interactive tutorial
    serviceDesk: '',             // your Jira service desk portal
    access: '',                  // how to request access
  },
};
