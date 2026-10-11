// WEAVE's panel list: the one file to edit to change what the page (and later the quilt) shows.
// PLACEHOLDER GUESS: these 12 panels are a stand-in launch set, not a decision.
// Order is the quilt's, row-major from the top left (4 columns x 3 rows).
// Fields: id and name are non-empty strings; status is 'live', 'planned' or 'suggest';
// since is a release string such as '1.0' (never a number); sample is { value, unit } or null.
// Every figure is sample data.
window.WEAVE_PANELS = {
  release: { version: '1.1', date: '2026-10-09', label: 'sample release' },
  newsWindowDays: 7,
  panels: [
    { id: 'manpower', name: 'Manpower', icon: 'people', fabric: 'coalesce-people', status: 'live', since: '1.0', sample: { value: 248, unit: 'assigned' }, blurb: "Who's on board, inbound and outbound: what Coalesce does today." },
    { id: 'hiring', name: 'Hiring', icon: 'person-plus', fabric: 'mustard-calico', status: 'live', since: '1.0', sample: { value: 4, unit: 'open positions' }, blurb: 'Open positions and where each hire stands.' },
    { id: 'training', name: 'Training', icon: 'mortarboard', fabric: 'indigo-dots', status: 'live', since: '1.0', sample: { value: '87%', unit: 'current' }, blurb: "Who's current on required training, and who's due." },
    { id: 'awards', name: 'Awards', icon: 'ribbon', fabric: 'rose-gingham', status: 'live', since: '1.0', sample: { value: 3, unit: 'to review' }, blurb: 'Nominations waiting for review.' },
    { id: 'promotions', name: 'Promotions', icon: 'chevrons', fabric: 'sage-stripe', status: 'planned', sample: null, blurb: 'Promotion boards and eligibility.' },
    { id: 'travel', name: 'Travel', icon: 'airplane', fabric: 'sky-chambray', status: 'live', since: '1.1', sample: { value: 12, unit: 'trips pending' }, blurb: 'Trip requests and approvals.' },
    { id: 'feedback', name: 'Feedback', icon: 'speech', fabric: 'plum-plaid', status: 'planned', sample: null, blurb: 'Feedback, in both directions.' },
    { id: 'actions', name: 'Action Tracking', icon: 'checklist', fabric: 'brick-solid', status: 'live', since: '1.0', sample: { value: 9, unit: 'open (2 overdue)' }, blurb: 'Taskers and action items with due dates.' },
    { id: 'oversight', name: 'Oversight', icon: 'magnifier', fabric: 'olive-calico', status: 'planned', sample: null, blurb: 'Reviews, inspections and findings.' },
    { id: 'access', name: 'Building Access', icon: 'key', fabric: 'navy-dots', status: 'planned', sample: null, blurb: 'Badges and building access.' },
    { id: 'desks', name: 'Desk Allocation', icon: 'desk', fabric: 'terracotta-gingham', status: 'live', since: '1.1', sample: { value: 18, unit: 'desks free' }, blurb: "Who sits where, and what's free." },
    { id: 'suggest', name: 'Suggest a panel', fabric: 'muslin', status: 'suggest', sample: null, blurb: 'Have an idea for a panel?' },
  ],
};
