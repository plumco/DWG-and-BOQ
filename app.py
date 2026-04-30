"""
Huliot PPT Report Formatter — Phase 1
Applies master template formatting to team-submitted site visit reports.
"""

import streamlit as st
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree
import io
import copy
import json
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Huliot Report Formatter",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a5c38 0%, #2d8a56 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 { color: white; margin: 0; font-size: 1.8rem; }
    .main-header p  { color: #c8f0d8; margin: 0.3rem 0 0 0; font-size: 0.95rem; }

    .step-card {
        background: #f8fffe;
        border: 1.5px solid #2d8a56;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1rem;
    }
    .step-number {
        background: #2d8a56;
        color: white;
        border-radius: 50%;
        width: 28px; height: 28px;
        display: inline-flex;
        align-items: center; justify-content: center;
        font-weight: bold; font-size: 0.85rem;
        margin-right: 0.5rem;
    }
    .status-box {
        background: #e8f5e9;
        border-left: 4px solid #2d8a56;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-size: 0.88rem;
    }
    .warn-box {
        background: #fff3e0;
        border-left: 4px solid #f57c00;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-size: 0.88rem;
    }
    .metric-row { display: flex; gap: 1rem; margin: 0.8rem 0; }
    .metric-box {
        flex: 1;
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.8rem;
        text-align: center;
    }
    .metric-box .val { font-size: 1.6rem; font-weight: bold; color: #1a5c38; }
    .metric-box .lbl { font-size: 0.75rem; color: #666; }
    div[data-testid="stFileUploader"] { border: 2px dashed #2d8a56 !important; border-radius: 10px; }
    .stButton > button {
        background: #1a5c38;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 2rem;
        font-size: 1rem;
        font-weight: 600;
        width: 100%;
    }
    .stButton > button:hover { background: #2d8a56; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SLIDE CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_slide(index: int, total: int) -> str:
    """Classify slide as cover | content | closing."""
    if index == 0:
        return "cover"
    if index == total - 1:
        return "closing"
    return "content"


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE PROFILE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _safe_rgb(font):
    try:
        if font.color and font.color.type:
            return font.color.rgb
    except Exception:
        pass
    return None


def extract_text_profile(slide):
    """
    Returns list of shape profiles with font info for every text shape.
    Shapes are tagged by their rough role (title / body / footer).
    """
    profiles = []
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        role = _guess_shape_role(shape, slide)
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                if not run.text.strip():
                    continue
                f = run.font
                profiles.append({
                    "role": role,
                    "name": f.name,
                    "size": f.size,
                    "bold": f.bold,
                    "italic": f.italic,
                    "color": _safe_rgb(f),
                    "alignment": para.alignment,
                    "space_before": para.space_before,
                    "space_after": para.space_after,
                    "line_spacing": para.line_spacing,
                })
    return profiles


def _guess_shape_role(shape, slide) -> str:
    """Heuristically guess title / footer / body."""
    name_lower = shape.name.lower()
    if "title" in name_lower:
        return "title"
    if "footer" in name_lower or "date" in name_lower or "slide number" in name_lower:
        return "footer"
    # positional: if top is in bottom 15% of slide height → footer
    try:
        slide_h = slide.part.slide_layout.slide_master.slide_height or Emu(6858000)
    except Exception:
        slide_h = Emu(6858000)  # standard 19.05 cm
    if shape.top and shape.top > slide_h * 0.82:
        return "footer"
    if shape.top and shape.top < slide_h * 0.25:
        return "title"
    return "body"


def extract_image_profile(slide):
    """Extract all image bounding boxes from a slide."""
    imgs = []
    for shape in slide.shapes:
        if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
            imgs.append({
                "left": shape.left,
                "top": shape.top,
                "width": shape.width,
                "height": shape.height,
            })
    return imgs


def build_template_profile(prs: Presentation) -> dict:
    """
    Build a full profile dict from the template:
      { 'cover': {...}, 'content': {...}, 'closing': {...} }
    Each entry has 'fonts' (by role) and 'images' (list of boxes).
    """
    slides = list(prs.slides)
    total = len(slides)
    profile = {}

    for idx, slide in enumerate(slides):
        stype = classify_slide(idx, total)
        if stype in profile:
            continue  # first occurrence wins

        text_profiles = extract_text_profile(slide)
        # Aggregate: per role, take the first non-None value
        fonts_by_role = {}
        for tp in text_profiles:
            r = tp["role"]
            if r not in fonts_by_role:
                fonts_by_role[r] = {k: tp[k] for k in ("name", "size", "bold", "italic", "color", "alignment", "space_before", "space_after", "line_spacing")}

        profile[stype] = {
            "fonts": fonts_by_role,
            "images": extract_image_profile(slide),
        }

    # Fallback: if no closing slide, copy content
    if "closing" not in profile and "content" in profile:
        profile["closing"] = copy.deepcopy(profile["content"])
    if "cover" not in profile and "content" in profile:
        profile["cover"] = copy.deepcopy(profile["content"])

    return profile


# ─────────────────────────────────────────────────────────────────────────────
# FORMATTING ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _apply_run_font(run, font_info: dict, opts: dict):
    """Apply font_info to a single run."""
    f = run.font
    if opts.get("fix_font_name") and font_info.get("name"):
        f.name = font_info["name"]
    if opts.get("fix_font_size") and font_info.get("size"):
        f.size = font_info["size"]
    if opts.get("fix_bold") and font_info.get("bold") is not None:
        f.bold = font_info["bold"]
    if opts.get("fix_color") and font_info.get("color"):
        try:
            f.color.rgb = font_info["color"]
        except Exception:
            pass


def _apply_para_spacing(para, font_info: dict, opts: dict):
    """Apply paragraph spacing from font_info."""
    if not opts.get("fix_spacing"):
        return
    try:
        if font_info.get("space_before") is not None:
            para.space_before = font_info["space_before"]
        if font_info.get("space_after") is not None:
            para.space_after = font_info["space_after"]
        if font_info.get("line_spacing") is not None:
            para.line_spacing = font_info["line_spacing"]
    except Exception:
        pass


def format_slide_text(slide, fonts_by_role: dict, opts: dict, changes: list):
    """Apply template font profile to all text shapes in a slide."""
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        role = _guess_shape_role(shape, slide)
        font_info = fonts_by_role.get(role) or fonts_by_role.get("body") or {}
        if not font_info:
            continue

        for para in shape.text_frame.paragraphs:
            _apply_para_spacing(para, font_info, opts)
            for run in para.runs:
                old_name = run.font.name
                old_size = run.font.size
                _apply_run_font(run, font_info, opts)
                if run.font.name != old_name or run.font.size != old_size:
                    changes.append(f"Font fixed in shape '{shape.name}' [{role}]")
                    break  # one change log per shape is enough


def format_slide_images(slide, img_profiles: list, opts: dict, changes: list):
    """Reposition and resize images to match template positions."""
    if not opts.get("fix_images") or not img_profiles:
        return

    pictures = [s for s in slide.shapes if s.shape_type == 13]
    if not pictures:
        return

    for idx, pic in enumerate(pictures):
        # Use the matching template slot; if more images than template has, use last slot
        slot = img_profiles[min(idx, len(img_profiles) - 1)]
        old_box = (pic.left, pic.top, pic.width, pic.height)
        try:
            pic.left   = slot["left"]
            pic.top    = slot["top"]
            pic.width  = slot["width"]
            pic.height = slot["height"]
            new_box = (pic.left, pic.top, pic.width, pic.height)
            if old_box != new_box:
                changes.append(f"Image {idx+1} repositioned/resized on slide")
        except Exception as e:
            changes.append(f"⚠ Image {idx+1} could not be repositioned: {e}")


def format_report(template_prs: Presentation, report_prs: Presentation, opts: dict) -> tuple:
    """
    Main entry: format report using template profile.
    Returns (formatted_prs, list_of_changes, stats_dict).
    """
    profile = build_template_profile(template_prs)
    total = len(report_prs.slides)
    all_changes = []
    stats = {"slides": total, "font_fixes": 0, "image_fixes": 0, "slides_touched": 0}

    for idx, slide in enumerate(report_prs.slides):
        stype = classify_slide(idx, total)
        slide_profile = profile.get(stype, profile.get("content", {}))
        slide_changes = []

        format_slide_text(slide, slide_profile.get("fonts", {}), opts, slide_changes)
        format_slide_images(slide, slide_profile.get("images", []), opts, slide_changes)

        if slide_changes:
            stats["slides_touched"] += 1
            for c in slide_changes:
                if "Font" in c:
                    stats["font_fixes"] += 1
                if "Image" in c:
                    stats["image_fixes"] += 1
                all_changes.append(f"Slide {idx+1} [{stype}] — {c}")

    return report_prs, all_changes, stats


# ─────────────────────────────────────────────────────────────────────────────
# PPTX I/O HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_prs(uploaded_file) -> Presentation:
    return Presentation(io.BytesIO(uploaded_file.read()))


def save_prs(prs: Presentation) -> bytes:
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def describe_template(prs: Presentation) -> dict:
    """Return quick summary of template for display."""
    profile = build_template_profile(prs)
    summary = {}
    for stype, data in profile.items():
        fonts = data.get("fonts", {})
        body = fonts.get("body") or fonts.get("title") or {}
        summary[stype] = {
            "font_name": body.get("name", "—"),
            "font_size_pt": round(body["size"].pt, 1) if body.get("size") else "—",
            "bold": body.get("bold"),
            "image_slots": len(data.get("images", [])),
        }
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

if "template_bytes" not in st.session_state:
    st.session_state.template_bytes = None
if "template_name" not in st.session_state:
    st.session_state.template_name = None
if "template_saved" not in st.session_state:
    st.session_state.template_saved = False

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="main-header">
  <h1>🔧 Huliot PPT Report Formatter</h1>
  <p>Auto-format team site visit reports to your standard template — Phase 1</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR — TEMPLATE MANAGEMENT & OPTIONS
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📁 Master Template")

    if st.session_state.template_saved:
        st.success(f"✅ Template loaded: **{st.session_state.template_name}**")
        if st.button("🔄 Replace Template"):
            st.session_state.template_bytes = None
            st.session_state.template_saved = False
            st.rerun()

        # Show template summary
        try:
            prs_tmp = Presentation(io.BytesIO(st.session_state.template_bytes))
            summary = describe_template(prs_tmp)
            st.markdown("**Template Profile:**")
            for stype, info in summary.items():
                st.markdown(f"*{stype.title()}* — `{info['font_name']}` {info['font_size_pt']}pt · {info['image_slots']} img slot(s)")
        except Exception:
            pass
    else:
        tpl_file = st.file_uploader(
            "Upload your standard PPT template",
            type=["pptx"],
            key="template_upload",
            help="Upload once — it stays loaded for all reports this session."
        )
        if tpl_file:
            st.session_state.template_bytes = tpl_file.read()
            st.session_state.template_name = tpl_file.name
            st.session_state.template_saved = True
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Formatting Options")

    fix_font_name  = st.checkbox("Font name (e.g. Book Antiqua)", value=True)
    fix_font_size  = st.checkbox("Font size",                      value=True)
    fix_bold       = st.checkbox("Bold / normal style",            value=True)
    fix_color      = st.checkbox("Font color",                     value=True)
    fix_spacing    = st.checkbox("Line & paragraph spacing",       value=True)
    fix_images     = st.checkbox("Photo size & position",          value=True)

    opts = {
        "fix_font_name": fix_font_name,
        "fix_font_size":  fix_font_size,
        "fix_bold":       fix_bold,
        "fix_color":      fix_color,
        "fix_spacing":    fix_spacing,
        "fix_images":     fix_images,
    }

    st.markdown("---")
    st.markdown("### ℹ️ How it works")
    st.markdown("""
1. Upload template once (saved this session)
2. Upload team's raw report
3. Click **Format Report**
4. Download clean PPT
    """)
    st.caption("Phase 1 — Formatting only. Content is preserved.")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT — UPLOAD + FORMAT
# ─────────────────────────────────────────────────────────────────────────────

if not st.session_state.template_saved:
    st.info("👈 Start by uploading your **master template** in the sidebar.")
    st.stop()

col1, col2 = st.columns([1.1, 0.9])

with col1:
    st.markdown("### 📤 Upload Team Report")
    report_file = st.file_uploader(
        "Drop the raw team PPT report here",
        type=["pptx"],
        key="report_upload",
        label_visibility="collapsed"
    )

    if report_file:
        st.markdown(f"""
        <div class="status-box">
        📄 <b>{report_file.name}</b><br>
        Size: {report_file.size / 1024:.0f} KB
        </div>
        """, unsafe_allow_html=True)

        try:
            report_bytes_raw = report_file.read()
            prs_check = Presentation(io.BytesIO(report_bytes_raw))
            n_slides = len(prs_check.slides)
            n_imgs = sum(
                1 for slide in prs_check.slides
                for shape in slide.shapes if shape.shape_type == 13
            )
            st.markdown(f"""
            <div class="metric-row">
              <div class="metric-box"><div class="val">{n_slides}</div><div class="lbl">Slides</div></div>
              <div class="metric-box"><div class="val">{n_imgs}</div><div class="lbl">Photos</div></div>
            </div>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Could not read report: {e}")
            st.stop()

        if st.button("🚀 Format Report Now"):
            with st.spinner("Applying template formatting…"):
                try:
                    # Fresh load of both files
                    prs_template = Presentation(io.BytesIO(st.session_state.template_bytes))
                    prs_report   = Presentation(io.BytesIO(report_bytes_raw))

                    formatted_prs, changes, stats = format_report(prs_template, prs_report, opts)
                    formatted_bytes = save_prs(formatted_prs)

                    # Store results in session state
                    st.session_state["formatted_bytes"]  = formatted_bytes
                    st.session_state["formatted_changes"] = changes
                    st.session_state["formatted_stats"]   = stats
                    st.session_state["formatted_name"]    = (
                        report_file.name.replace(".pptx", "") +
                        "_formatted_" + datetime.now().strftime("%d%b%Y") + ".pptx"
                    )
                except Exception as e:
                    st.error(f"Formatting failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())

with col2:
    st.markdown("### 📥 Download Result")

    if "formatted_bytes" in st.session_state and st.session_state["formatted_bytes"]:
        stats   = st.session_state["formatted_stats"]
        changes = st.session_state["formatted_changes"]
        fname   = st.session_state["formatted_name"]

        st.success("✅ Formatting complete!")

        st.markdown(f"""
        <div class="metric-row">
          <div class="metric-box"><div class="val">{stats['slides_touched']}</div><div class="lbl">Slides Fixed</div></div>
          <div class="metric-box"><div class="val">{stats['font_fixes']}</div><div class="lbl">Font Fixes</div></div>
          <div class="metric-box"><div class="val">{stats['image_fixes']}</div><div class="lbl">Image Fixes</div></div>
        </div>
        """, unsafe_allow_html=True)

        st.download_button(
            label="⬇️ Download Formatted PPT",
            data=st.session_state["formatted_bytes"],
            file_name=fname,
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )

        if changes:
            with st.expander(f"📋 Change log ({len(changes)} changes)", expanded=False):
                for c in changes:
                    st.markdown(f"- {c}")
        else:
            st.markdown("""
            <div class="warn-box">
            ℹ No formatting differences detected. The report may already match the template,
            or the template has no explicit font/size values set on runs.
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center; color:#aaa; padding: 3rem 1rem;">
        <div style="font-size:3rem">📋</div>
        <div>Upload a report and click<br><b>Format Report Now</b></div>
        </div>
        """, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption("Huliot Pipes & Fittings Pvt Ltd · PPT Formatter v1.0 · Phase 1 · Built with python-pptx + Streamlit")
