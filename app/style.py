"""Look and feel for the dashboard: CSS plus small HTML helpers.

All colours come from Streamlit theme variables or translucent tints, so the same
styles read well in light and dark mode. The layout is mobile-first and widens at 700 px.
"""
from html import escape

CSS = """
<style>
.stApp {
  --sv-accent: #4f46e5;
  --sv-radius: 16px;
  --sv-card: color-mix(in srgb, currentColor 5%, transparent);
  --sv-border: color-mix(in srgb, currentColor 14%, transparent);
  --sv-soft: color-mix(in srgb, currentColor 6%, transparent);
  --sv-muted: color-mix(in srgb, currentColor 62%, transparent);
}

/* ---- page frame -------------------------------------------------------- */
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container {
  max-width: 1100px;
  padding: 1.2rem 1rem 5rem;
}
@media (min-width: 700px) { .block-container { padding: 2rem 2rem 4rem; } }
h1, h2, h3 { letter-spacing: -0.02em; }
h3 { font-size: 1.15rem !important; margin-top: .6rem; }

/* ---- hero -------------------------------------------------------------- */
.sv-hero {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 55%, #0ea5e9 100%);
  color: #fff;
  border-radius: 22px;
  padding: 1.25rem 1.25rem 1.1rem;
  margin-bottom: 1.1rem;
  box-shadow: 0 10px 30px -12px rgba(79, 70, 229, .55);
}
.sv-hero h1 { color: #fff; font-size: 1.55rem; margin: 0 0 .25rem; padding: 0; line-height: 1.15; }
.sv-hero p { margin: 0; opacity: .9; font-size: .95rem; }
.sv-pills { display: flex; flex-wrap: wrap; gap: .4rem; margin-top: .8rem; }
.sv-pill {
  background: rgba(255,255,255,.18);
  border: 1px solid rgba(255,255,255,.28);
  border-radius: 999px;
  padding: .18rem .65rem;
  font-size: .78rem;
  font-weight: 600;
  backdrop-filter: blur(4px);
}
@media (min-width: 700px) {
  .sv-hero { padding: 1.7rem 2rem 1.5rem; }
  .sv-hero h1 { font-size: 2.1rem; }
}

/* ---- tabs -------------------------------------------------------------- */
div[data-baseweb="tab-list"] { gap: .25rem; overflow-x: auto; }
button[data-baseweb="tab"] { height: 3rem; padding: 0 1rem; font-weight: 600; }

/* ---- step guide -------------------------------------------------------- */
.sv-steps { display: grid; grid-template-columns: 1fr; gap: .6rem; margin: .4rem 0 1rem; }
@media (min-width: 700px) { .sv-steps { grid-template-columns: repeat(3, 1fr); } }
.sv-step {
  display: flex; gap: .75rem; align-items: center;
  background: var(--sv-card);
  border: 1px solid var(--sv-border);
  border-radius: var(--sv-radius);
  padding: .75rem .9rem;
}
.sv-step b.n {
  flex: none; width: 1.9rem; height: 1.9rem; border-radius: 50%;
  display: grid; place-items: center;
  background: var(--sv-accent); color: #fff; font-size: .9rem;
}
.sv-step span { font-size: .88rem; color: var(--sv-muted); line-height: 1.3; }
.sv-step strong { display: block; color: currentColor; font-size: .95rem; }

/* ---- KPI tiles --------------------------------------------------------- */
.sv-kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: .7rem; margin: .4rem 0 1.1rem; }
@media (min-width: 700px) { .sv-kpis { grid-template-columns: repeat(4, 1fr); gap: 1rem; } }
.sv-kpi {
  background: var(--sv-card);
  border: 1px solid var(--sv-border);
  border-radius: var(--sv-radius);
  padding: .85rem 1rem;
  position: relative; overflow: hidden;
}
.sv-kpi::before { content: ""; position: absolute; inset: 0 auto 0 0; width: 4px; background: var(--k, var(--sv-accent)); }
.sv-kpi .v { font-size: 1.9rem; font-weight: 750; line-height: 1.1; font-variant-numeric: tabular-nums; }
.sv-kpi .l { font-size: .78rem; color: var(--sv-muted); text-transform: uppercase; letter-spacing: .05em; font-weight: 600; }

/* ---- item cards -------------------------------------------------------- */
.sv-cards { display: grid; grid-template-columns: 1fr; gap: .7rem; margin: .3rem 0 1rem; }
.sv-card {
  background: var(--sv-card);
  border: 1px solid var(--sv-border);
  border-left: 5px solid var(--c);
  border-radius: var(--sv-radius);
  padding: .85rem 1rem;
}
.sv-card .top { display: flex; justify-content: space-between; align-items: flex-start; gap: .6rem; }
.sv-card .name { font-weight: 700; font-size: 1.02rem; }
.sv-card .sub { color: var(--sv-muted); font-size: .8rem; }
.sv-chip {
  flex: none; white-space: nowrap;
  background: color-mix(in srgb, var(--c) 18%, transparent);
  color: color-mix(in srgb, var(--c) 65%, currentColor);
  border: 1px solid color-mix(in srgb, var(--c) 40%, transparent);
  border-radius: 999px; padding: .15rem .65rem; font-size: .75rem; font-weight: 700;
}
.sv-nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: .5rem; margin-top: .7rem; text-align: center; }
.sv-nums div { background: var(--sv-soft); border-radius: 12px; padding: .45rem .2rem; }
.sv-nums b { display: block; font-size: 1.25rem; font-variant-numeric: tabular-nums; }
.sv-nums span { font-size: .68rem; color: var(--sv-muted); text-transform: uppercase; letter-spacing: .05em; }
.sv-card .act { margin-top: .65rem; font-size: .84rem; color: var(--sv-muted); line-height: 1.35; }
.sv-conf { height: 5px; border-radius: 3px; background: var(--sv-soft); margin-top: .6rem; overflow: hidden; }
.sv-conf i { display: block; height: 100%; background: var(--c); border-radius: 3px; }

/* ---- generic polish ---------------------------------------------------- */
.sv-meta { color: var(--sv-muted); font-size: .85rem; margin: .2rem 0 .6rem; }
.sv-meta b { color: currentColor; }
.sv-empty {
  text-align: center; padding: 2rem 1rem; border: 2px dashed var(--sv-border);
  border-radius: var(--sv-radius); color: var(--sv-muted);
}
div[data-testid="stFileUploaderDropzone"], div[data-testid="stCameraInput"] {
  border-radius: var(--sv-radius);
}
div[data-testid="stImage"], div[data-testid="stImage"] img { width: 100% !important; max-width: 100%; }
div[data-testid="stImage"] img { border-radius: var(--sv-radius); height: auto; }
div[data-testid="stCameraInput"] video, div[data-testid="stCameraInput"] img { border-radius: var(--sv-radius); }
div[data-testid="stAlert"] { border-radius: 14px; }
.stButton > button, .stDownloadButton > button {
  border-radius: 12px; font-weight: 650; min-height: 2.9rem;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #4f46e5, #7c3aed); border: 0; color: #fff;
}
@media (max-width: 699px) {
  div[data-testid="stElementContainer"]:has(> div[data-testid="stButton"]),
  div[data-testid="stElementContainer"]:has(> div[data-testid="stDownloadButton"]),
  div[data-testid="stButton"], div[data-testid="stDownloadButton"] { width: 100% !important; }
  div[data-testid="stButton"] > button, div[data-testid="stDownloadButton"] > button { width: 100% !important; }
}
@media (min-width: 700px) {
  .stButton > button, .stDownloadButton > button { width: auto; min-width: 12rem; }
}
div[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; border: 1px solid var(--sv-border); }
section[data-testid="stSidebar"] { border-right: 1px solid var(--sv-border); }

/* Extra room for thumbs on phones */
@media (max-width: 699px) {
  div[data-testid="stRadio"] label { padding: .35rem 0; }
  div[data-testid="stExpander"] summary { padding: .8rem 1rem; }
}
</style>
"""

# Accent colour per status (readable on light and dark backgrounds).
STATUS_ACCENT = {
    "match": "#16a34a",
    "minor": "#d97706",
    "major": "#dc2626",
    "stockout": "#b91c1c",
    "overcount": "#2563eb",
    "no_record": "#6b7280",
}


def hero(title: str, subtitle: str, pills: list) -> str:
    chips = "".join(f'<span class="sv-pill">{escape(p)}</span>' for p in pills)
    return (f'<div class="sv-hero"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p>'
            f'<div class="sv-pills">{chips}</div></div>')


def steps() -> str:
    items = [("Capture", "Take or upload a photo or video"),
             ("Count", "The model detects and counts items"),
             ("Compare", "Counts are checked against records")]
    body = "".join(f'<div class="sv-step"><b class="n">{i}</b><span><strong>{escape(t)}</strong>{escape(d)}</span></div>'
                   for i, (t, d) in enumerate(items, 1))
    return f'<div class="sv-steps">{body}</div>'


def kpis(items: list) -> str:
    """items: (label, value, colour or None)."""
    body = "".join(
        f'<div class="sv-kpi" style="--k:{c or "var(--sv-accent)"}"><div class="v">{escape(str(v))}</div>'
        f'<div class="l">{escape(l)}</div></div>' for l, v, c in items)
    return f'<div class="sv-kpis">{body}</div>'


def _num(value, signed=False) -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        value = round(value, 1)
        if value == int(value):
            value = int(value)
    return f"{value:+}" if signed and value else str(value)


def item_cards(rows: list, status_info: dict) -> str:
    cards = []
    for r in rows:
        colour = STATUS_ACCENT.get(r["status"], "#6b7280")
        label, action = status_info[r["status"]][0], status_info[r["status"]][1]
        conf = r.get("confidence")
        conf_bar = ""
        if isinstance(conf, (int, float)):
            pct = max(0, min(100, conf * 100 if conf <= 1 else conf))
            conf_bar = (f'<div class="sv-conf" title="Detection confidence {pct:.0f}%"><i style="width:{pct:.0f}%"></i></div>'
                        f'<div class="sub" style="margin-top:.25rem">Confidence {pct:.0f}%</div>')
        pct_txt = f' ({_num(r["variance_pct"], True)}%)' if r.get("variance_pct") is not None else ""
        cards.append(
            f'<div class="sv-card" style="--c:{colour}">'
            f'<div class="top"><div><div class="name">{escape(str(r["item_name"]))}</div>'
            f'<div class="sub">{escape(str(r["sku"]))} · {escape(str(r["location"] or ""))}</div></div>'
            f'<span class="sv-chip">{escape(label)}</span></div>'
            f'<div class="sv-nums"><div><b>{_num(r["detected"])}</b><span>Detected</span></div>'
            f'<div><b>{_num(r["recorded"])}</b><span>Recorded</span></div>'
            f'<div><b>{_num(r["variance"], True)}</b><span>Variance{escape(pct_txt)}</span></div></div>'
            f'<div class="act">{escape(action)}</div>{conf_bar}</div>')
    return f'<div class="sv-cards">{"".join(cards)}</div>'


def empty(text: str) -> str:
    return f'<div class="sv-empty">{escape(text)}</div>'
