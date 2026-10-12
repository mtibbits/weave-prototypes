// blazeAhead tour: the words on the signposts and on each stop's card. Edit freely.
//
// DRAFT COPY: written from short descriptions of each feature. Replace it with your own words.
//
// The trail has exactly four stop scenes, in this order: the stream (continuity), base camp (scaffolding),
// the map board (knowledge) and the launch clearing (in-flight). Stops map to them in order; extra stops are
// ignored. Anything you leave out falls back to the text shipped in js/content.js.
// `sign` is the word on the signposts (keep it short: it has to fit on an 18-inch board).
window.BLAZEAHEAD_TOUR = {
  trailhead: { sign: 'Trailhead', tourSign: 'The tour' },
  end: { sign: 'Download' },
  stops: [
    {
      sign: 'Continuity',
      title: 'The continuity proxy',
      paragraphs: [
        'Our network gets busy. When a service answers with a 429 or a 503, an event stream hiccups, or a reply '
        + 'breaks off mid-stream, the continuity proxy absorbs it and carries on. Your Claude Code session keeps going '
        + 'instead of falling over.',
      ],
      points: ['Absorbs 429 and 503 responses', 'Rides out SSE glitches and stream errors', 'Keeps long sessions flowing'],
    },
    {
      sign: 'Scaffolding',
      title: 'Scaffold your environment',
      paragraphs: [
        'blazeAhead sets up your development environment and mints the personal access tokens you need, so you start '
        + 'the trail with every key already on the ring.',
      ],
      points: ['Tokens for Jira, Confluence, GitLab and Artifactory', 'A development environment ready to work in'],
    },
    {
      sign: 'Knowledge',
      title: 'The knowledge base',
      paragraphs: [
        'Every internal tool, charted as trails from one trailhead. Step through the trails, or unfold the map and '
        + 'open a destination.',
      ],
      points: [],
      // The trail map on the kiosk: trails from the centre, each with its destinations. A destination can lead on to
      // more (`next`). Up to 5 trails, 5 destinations on a trail, 2 onward stops per destination, and 25 stops in all.
      // A `url` that starts with https:// or http:// makes the name a link on the card and on the unfolded map; leave
      // it '' and the name shows as plain text. The map lays itself out, so there is nothing to position.
      map: {
        centre: 'blazeAhead',
        trails: [
          { name: 'Getting connected', destinations: [
            { name: 'Proxy', url: '' },
            { name: 'GitLab', url: '' },
            { name: 'Certificates', url: '' },
            { name: 'Access tokens', url: '' },
          ] },
          { name: 'Agentic workflow', destinations: [
            { name: 'devAgent', url: '' },
            { name: 'Jira', url: '' },
            { name: 'Claude skills', url: '' },
            { name: 'Claude plugins', url: '' },
          ] },
          { name: 'Language specific', destinations: [
            { name: 'Java', url: '', next: [{ name: 'Artifactory', url: '' }] },
            { name: 'C++', url: '', next: [{ name: 'SonarQube', url: '' }] },
            { name: 'Python', url: '', next: [{ name: 'PyPI mirror', url: '' }] },
          ] },
          { name: 'Infrastructure', destinations: [
            { name: 'Deployment', url: '', next: [{ name: 'AWS account', url: '' }] },
            { name: 'Terraform', url: '' },
            { name: 'Kubernetes', url: '' },
          ] },
          { name: 'Corporate knowledge', destinations: [
            { name: 'Confluence', url: '' },
            { name: 'Onboarding', url: '' },
            { name: 'Security & policy', url: '' },
          ] },
        ],
      },
    },
    {
      sign: 'In Flight',
      title: 'The In Flight queue',
      paragraphs: [
        'In Flight connects to Jira and runs prompts through the devAgent workflow straight from Jira issues. It isn’t '
        + 'about engineering one prompt; it’s about keeping hundreds of them moving.',
      ],
      points: ['Reads your queue from Jira', 'Runs each issue through devAgent', 'Keeps hundreds of prompts moving'],
    },
  ],
  // The three arms of the signpost on the Help page.
  help: { signs: { left: 'Issues', right: 'Docs', ahead: 'Tour' } },
  // What each rock in the stream stands for (hover a rock at the first stop). Five rocks, in order.
  rocks: ['429 Too Many Requests', '503 Service Unavailable', 'SSE glitch', 'Stream error', 'Timeout'],
};
