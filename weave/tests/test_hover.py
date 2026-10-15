"""#10's hover: the tooltip (dom.js and weave.css, on a blank page) and, on the live page, naming and lifting a block."""
from helpers import LINK_CSS, PLANNED_WORDS, SEWN_WORDS, SUGGEST_WORDS

# A 528 x 330 .hero-stage (weave.css's aspect ratio) with weave.css linked, and dom.js as D.
TIP_JS = LINK_CSS + r"""
    const D = await import('/public/js/dom.js');
    const stage = document.createElement('div');
    stage.className = 'hero-stage';
    stage.style.width = '528px';
    document.body.append(stage);
"""


def tip(js, body):
    return js(TIP_JS + body)


def test_tooltip_is_text_only_and_hidden_from_assistive_tech(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        const made = { children: stage.querySelectorAll('[data-tooltip]').length, parent: t.parentElement === stage,
                       aria: t.getAttribute('aria-hidden'), hidden: t.hidden };
        const name = '<img src=x onerror="window.__xss=1">';
        D.showTooltip(t, { name, face: 'sewn' }, 10, 20);
        await new Promise((resolve) => setTimeout(resolve, 50));
        const shown = { name: t.querySelector('.hero-tip-name').textContent === name, elements: t.querySelectorAll('*').length,
                        xss: window.__xss === undefined, hidden: t.hidden };
        D.hideTooltip(t);
        return { made, shown, after: t.hidden };
    """)
    assert r["made"] == {"children": 1, "parent": True, "aria": "true", "hidden": True}
    assert r["shown"] == {"name": True, "elements": 2, "xss": True, "hidden": False}
    assert r["after"] is True


def test_tooltip_flips_inside_the_stage(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        const box = (el) => { const b = el.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; };
        D.showTooltip(t, { name: 'Promotions and a long name', face: 'planned' }, 500, 300);
        const corner = { tip: box(t), stage: box(stage) };
        D.showTooltip(t, { name: 'Manpower', face: 'sewn' }, 10, 20);
        return { corner, near: [t.offsetLeft, t.offsetTop], size: [stage.clientWidth, stage.clientHeight],
                 display: [...t.children].map((c) => getComputedStyle(c).display),
                 style: (({ position, pointerEvents, opacity }) => ({ position, pointerEvents, opacity }))(getComputedStyle(t)) };
    """)
    assert r["size"] == [528, 330]
    (l, t, rt, b), (sl, st, sr, sb) = r["corner"]["tip"], r["corner"]["stage"]
    assert l >= sl and t >= st and rt <= sr and b <= sb, r["corner"]
    assert r["near"] == [22, 32]
    assert r["display"] == ["block", "block"]
    assert r["style"] == {"position": "absolute", "pointerEvents": "none", "opacity": "1"}


def test_tooltip_status_words(js):
    r = tip(js, r"""
        const t = D.createTooltip(stage);
        return ['sewn', 'planned', 'suggest'].map((face) => {
          D.showTooltip(t, { name: 'X', face }, 10, 10);
          return t.querySelector('.hero-tip-status').textContent;
        });
    """)
    assert r == [SEWN_WORDS, PLANNED_WORDS, SUGGEST_WORDS]
