"""Shared visual system for the OMOP Mapping Review app.

A calm, healthcare-grade theme: one typeface, a restrained palette, generous
whitespace, hairline borders. No gradient banners, no decorative noise.
"""
import streamlit as st

# ---- palette ----------------------------------------------------------------
INK = "#1A2433"        # primary text
SLATE = "#5B6B7F"      # secondary text
MUTED = "#8593A8"      # tertiary / captions
LINE = "#E6EBF2"       # hairline borders
CANVAS = "#F7F9FC"     # app background
PRIMARY = "#0F6E8C"    # calm teal — the single accent
PRIMARY_D = "#0B5468"

GREEN = "#1CA774"
AMBER = "#D9920B"
CORAL = "#D87A5A"
RED = "#C0392B"

# legacy aliases (kept so older references don't break)
NAVY = INK
TEAL = PRIMARY
LAVA = PRIMARY

GAP_COLOR = {
    "mapped_standard": GREEN,
    "mapped_nonstandard": AMBER,
    "unmapped_vocab_gap": CORAL,
    "unmapped_s2cm_gap": RED,
}
GAP_LABEL = {
    "unmapped_vocab_gap": "Vocabulary gap",
    "unmapped_s2cm_gap": "Local code, no map",
    "mapped_nonstandard": "Non-standard",
    "mapped_standard": "Mapped",
}
STATUS_CHIP = {
    "open": (SLATE, "Open"),
    "in_review": (AMBER, "In review"),
    "reviewed": (AMBER, "Reviewed"),
    "approved": (GREEN, "Approved"),
    "committed": (PRIMARY, "Committed"),
}


def inject():
    st.markdown(f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
      html, body, [class*="css"], .stApp {{ font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }}
      .stApp {{ background:{CANVAS}; }}
      .block-container {{ padding-top:2.2rem; padding-bottom:3rem; max-width:1120px; }}
      #MainMenu, footer, header[data-testid="stHeader"] {{ visibility:hidden; }}

      /* sidebar — clean light rail */
      section[data-testid="stSidebar"] {{ background:#fff; border-right:1px solid {LINE}; }}
      section[data-testid="stSidebar"] .block-container {{ padding-top:1.4rem; }}
      section[data-testid="stSidebar"] h1,
      section[data-testid="stSidebar"] h2,
      section[data-testid="stSidebar"] h3 {{ font-size:.78rem; text-transform:uppercase;
        letter-spacing:.06em; color:{MUTED}; font-weight:600; }}

      /* page header */
      .ph {{ margin:0 0 1.6rem 0; padding-bottom:1.1rem; border-bottom:1px solid {LINE}; }}
      .ph .eyebrow {{ font-size:.72rem; font-weight:600; letter-spacing:.08em;
        text-transform:uppercase; color:{PRIMARY}; margin-bottom:.45rem; }}
      .ph h1 {{ font-size:1.55rem; font-weight:600; color:{INK}; margin:0; line-height:1.25; letter-spacing:-.01em; }}
      .ph p {{ font-size:.95rem; color:{SLATE}; margin:.45rem 0 0 0; line-height:1.55; text-wrap:pretty; }}

      /* section label */
      .sec {{ font-size:.82rem; font-weight:600; letter-spacing:.04em; text-transform:uppercase;
        color:{MUTED}; margin:1.6rem 0 .7rem 0; }}

      /* KPI */
      .kpi {{ background:#fff; border:1px solid {LINE}; border-radius:12px; padding:1.1rem 1.2rem; height:100%; }}
      .kpi .lab {{ font-size:.74rem; color:{MUTED}; font-weight:500; letter-spacing:.02em; }}
      .kpi .val {{ font-size:1.85rem; font-weight:600; color:{INK}; line-height:1.1; margin-top:.35rem; letter-spacing:-.01em; }}
      .kpi .sub {{ font-size:.8rem; color:{SLATE}; margin-top:.3rem; line-height:1.4; }}

      /* card */
      .card {{ background:#fff; border:1px solid {LINE}; border-radius:12px; padding:1rem 1.2rem; margin-bottom:.7rem; }}
      .code {{ font-family:'SF Mono',ui-monospace,Menlo,monospace; font-weight:600; font-size:1rem; color:{INK}; }}
      .meta {{ color:{MUTED}; font-size:.82rem; line-height:1.5; }}

      /* badges & chips */
      .badge {{ display:inline-block; padding:.15rem .55rem; border-radius:6px; font-size:.72rem; font-weight:600; color:#fff; }}
      .chip {{ display:inline-block; padding:.12rem .55rem; border-radius:6px; font-size:.72rem; font-weight:600; border:1px solid; }}

      .bar {{ height:6px; border-radius:6px; background:{LINE}; overflow:hidden; margin-top:.4rem; }}
      .bar > span {{ display:block; height:100%; background:{PRIMARY}; }}

      /* process flow — native steps */
      .flow {{ margin:.4rem 0 .2rem; }}
      .flow .step {{ display:flex; gap:1rem; padding-bottom:1.4rem; position:relative; }}
      .flow .step:last-child {{ padding-bottom:0; }}
      .flow .marker {{ flex:0 0 30px; position:relative; display:flex; justify-content:center; }}
      .flow .dot {{ width:30px; height:30px; border-radius:50%; background:{PRIMARY}; color:#fff;
        font-weight:600; font-size:.85rem; display:flex; align-items:center; justify-content:center; z-index:1; }}
      .flow .step:not(:last-child) .marker::before {{ content:''; position:absolute; left:14px; top:30px;
        bottom:-1.4rem; width:2px; background:{LINE}; }}
      .flow .body {{ padding-top:.2rem; }}
      .flow .t {{ font-size:.98rem; font-weight:600; color:{INK}; }}
      .flow .who {{ font-size:.72rem; font-weight:600; color:{PRIMARY}; text-transform:uppercase; letter-spacing:.04em; }}
      .flow .d {{ font-size:.88rem; color:{SLATE}; margin-top:.15rem; line-height:1.5; max-width:60ch; }}
      .loop {{ font-size:.85rem; color:{MUTED}; margin-top:.4rem; padding-left:calc(30px + 1rem); }}

      /* lifecycle stepper */
      .lc {{ display:flex; gap:.6rem; margin:.4rem 0 .4rem 0; }}
      .lc .stg {{ flex:1; background:#fff; border:1px solid {LINE}; border-radius:12px; padding:.9rem 1rem; }}
      .lc .stg .top {{ height:3px; border-radius:3px; margin:-.9rem -1rem .8rem -1rem;
        border-top-left-radius:12px; border-top-right-radius:12px; }}
      .lc .stg .num {{ font-size:1.7rem; font-weight:600; line-height:1; letter-spacing:-.01em; }}
      .lc .stg .nm {{ font-size:.76rem; font-weight:600; color:{INK}; text-transform:uppercase; letter-spacing:.04em; margin-top:.35rem; }}
      .lc .stg .ds {{ font-size:.74rem; color:{MUTED}; margin-top:.15rem; line-height:1.4; }}
      .lc .arr {{ display:flex; align-items:center; color:#C4CEDB; font-size:1.3rem; }}
    </style>
    """, unsafe_allow_html=True)


def header(title: str, subtitle: str = "", eyebrow: str = ""):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    sub = f"<p>{subtitle}</p>" if subtitle else ""
    st.markdown(f'<div class="ph">{eb}<h1>{title}</h1>{sub}</div>', unsafe_allow_html=True)


# backwards-compatible alias — old pages call hero(title, subtitle[, pill])
def hero(title: str, subtitle: str = "", pill: str = "OMOP Mapping Review"):
    header(title, subtitle, eyebrow=pill if pill else "")


def section(label: str):
    st.markdown(f'<div class="sec">{label}</div>', unsafe_allow_html=True)


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="lab">{label}</div>'
                 f'<div class="val">{value}</div><div class="sub">{sub}</div></div>',
                 unsafe_allow_html=True)


def gap_badge(gap_type: str) -> str:
    c = GAP_COLOR.get(gap_type, MUTED)
    return f'<span class="badge" style="background:{c}">{GAP_LABEL.get(gap_type, gap_type)}</span>'


def status_chip(status: str) -> str:
    c, lab = STATUS_CHIP.get(status, (MUTED, status))
    return f'<span class="chip" style="color:{c};border-color:{c}">{lab}</span>'


def priority_bar(pct: float) -> str:
    pct = max(2, min(100, float(pct or 0)))
    return f'<div class="bar"><span style="width:{pct}%"></span></div>'


def flow(steps, loop: str = ""):
    """steps: list of (title, who, description). Renders a native vertical step flow."""
    parts = ['<div class="flow">']
    for i, (title, who, desc) in enumerate(steps, 1):
        wh = f'<span class="who">{who}</span> &middot; ' if who else ""
        parts.append(
            f'<div class="step"><div class="marker"><span class="dot">{i}</span></div>'
            f'<div class="body"><div class="t">{title}</div>'
            f'<div class="d">{wh}{desc}</div></div></div>')
    parts.append("</div>")
    if loop:
        parts.append(f'<div class="loop">↻ {loop}</div>')
    st.markdown("".join(parts), unsafe_allow_html=True)


def lifecycle(stages):
    """stages: list of (name, count, desc, color). Horizontal stepper."""
    parts = ['<div class="lc">']
    for i, (name, count, desc, color) in enumerate(stages):
        if i:
            parts.append('<div class="arr">&rsaquo;</div>')
        parts.append(
            f'<div class="stg"><div class="top" style="background:{color}"></div>'
            f'<div class="num" style="color:{color}">{count}</div>'
            f'<div class="nm">{name}</div><div class="ds">{desc}</div></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)
