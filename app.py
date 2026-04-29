"""
Huliot Drawing Intelligence Platform
DXF Viewer + AI Analysis + BOQ Generator
"""

import streamlit as st
import pandas as pd
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io, os, re, math, base64, json, tempfile
import requests
from io import BytesIO

# ─── PAGE CONFIG ────────────────────────────────────────────────
st.set_page_config(
    page_title="Huliot DIP",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── STYLES ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600;700&display=swap');

html, body, .stApp { background:#0a0d13; color:#e8e8e0; font-family:'IBM Plex Sans', sans-serif; }

h1,h2,h3 { font-family:'Bebas Neue', sans-serif; letter-spacing:0.05em; }

.hero {
    background: linear-gradient(135deg, #0d2818 0%, #0a1a0a 50%, #0d1a2a 100%);
    border: 1px solid #1a5f3c;
    border-radius: 12px;
    padding: 2.5rem;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(26,95,60,0.15) 0%, transparent 60%);
    pointer-events: none;
}
.hero h1 { font-size:3.5rem; color:#00ff88; margin:0; line-height:1; }
.hero p { color:#8a8a7a; font-family:'IBM Plex Mono', monospace; font-size:0.85rem; margin-top:0.5rem; }

.stat-card {
    background: #0d1a12;
    border: 1px solid #1a5f3c;
    border-radius: 8px;
    padding: 1.2rem;
    text-align: center;
    transition: border-color 0.2s;
}
.stat-card:hover { border-color: #00ff88; }
.stat-card .val { font-size:2rem; font-weight:700; color:#00ff88; font-family:'Bebas Neue', sans-serif; }
.stat-card .lbl { font-size:0.7rem; color:#8a8a7a; text-transform:uppercase; letter-spacing:0.1em; margin-top:0.2rem; font-family:'IBM Plex Mono', monospace; }

.sh-card {
    background: #0d1a12;
    border: 1px solid #1a4a2a;
    border-left: 4px solid #00ff88;
    border-radius: 6px;
    padding: 1rem;
    margin-bottom: 0.8rem;
}
.sh-card .sh-label { font-family:'Bebas Neue', sans-serif; font-size:1.8rem; color:#00ff88; line-height:1; }
.sh-card .sh-type { font-family:'IBM Plex Mono', monospace; font-size:0.72rem; color:#8a8a7a; text-transform:uppercase; margin-bottom:0.5rem; }
.sh-card .fixture-row { display:flex; gap:1rem; margin-top:0.5rem; }
.sh-card .fix-item { background:#0a1409; border:1px solid #1a3a1a; border-radius:4px; padding:0.3rem 0.6rem; font-size:0.75rem; color:#b0c0b0; font-family:'IBM Plex Mono', monospace; }

.boq-header { background:#1a5f3c; color:white; padding:0.8rem 1rem; border-radius:6px 6px 0 0; font-family:'Bebas Neue', sans-serif; font-size:1.4rem; letter-spacing:0.1em; }

.status-ok { color:#00ff88; font-weight:600; }
.status-err { color:#ff4444; }
.status-warn { color:#ffaa00; }

.upload-zone {
    border: 2px dashed #1a5f3c;
    border-radius: 10px;
    padding: 3rem;
    text-align: center;
    background: #0d1a12;
    transition: all 0.2s;
}

.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem;
    color: #00ff88;
    letter-spacing: 0.08em;
    border-bottom: 1px solid #1a5f3c;
    padding-bottom: 0.5rem;
    margin-bottom: 1rem;
}

/* Streamlit overrides */
.stButton > button {
    background: #1a5f3c !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #00ff88 !important;
    color: #0a0d13 !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.82rem !important;
    color: #8a8a7a !important;
}
.stTabs [aria-selected="true"] {
    color: #00ff88 !important;
    border-bottom-color: #00ff88 !important;
}
.stNumberInput > div > div > input,
.stTextInput > div > div > input {
    background: #0d1a12 !important;
    border: 1px solid #1a5f3c !important;
    color: #e8e8e0 !important;
    border-radius: 4px !important;
}
div[data-testid="stDataFrame"] { border: 1px solid #1a5f3c; border-radius: 6px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ───────────────────────────────────────────────
for k, v in {
    'dxf_doc': None,
    'dxf_path': None,
    'drawing_image': None,
    'sh_data': [],
    'boq_df': None,
    'analysis_done': False
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── FUNCTIONS ───────────────────────────────────────────────────

def render_dxf_to_image(dxf_path, dpi=150):
    """Render DXF to PNG image using ezdxf + matplotlib"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        fig = plt.figure(figsize=(16, 10), facecolor='#0a0d13')
        ax = fig.add_axes([0, 0, 1, 1], facecolor='#0a0d13')
        
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        frontend = Frontend(ctx, backend)
        frontend.draw_layout(msp, finalize=True)
        
        # Style the axes
        ax.set_facecolor('#0a0d13')
        ax.tick_params(colors='#8a8a7a')
        for spine in ax.spines.values():
            spine.set_edgecolor('#1a5f3c')
        
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight',
                   facecolor='#0a0d13', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        return None

def get_dxf_stats(dxf_path):
    """Get basic stats from DXF file"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        stats = {'entities': {}, 'layers': set(), 'blocks': set(), 'texts': []}
        
        for entity in msp:
            etype = entity.dxftype()
            stats['entities'][etype] = stats['entities'].get(etype, 0) + 1
            
            if hasattr(entity.dxf, 'layer'):
                stats['layers'].add(entity.dxf.layer)
            
            if etype == 'INSERT':
                try:
                    stats['blocks'].add(entity.dxf.name)
                except: pass
            
            if etype in ('TEXT', 'MTEXT'):
                try:
                    t = entity.dxf.text if hasattr(entity.dxf, 'text') else ''
                    if t.strip():
                        stats['texts'].append(t.strip())
                except: pass
        
        stats['layers'] = sorted(list(stats['layers']))
        stats['blocks'] = sorted(list(stats['blocks']))
        
        # Find SH marks in texts
        sh_found = []
        for t in stats['texts']:
            m = re.search(r'SH\s*-?\s*(\d+)', t, re.IGNORECASE)
            if m:
                sh_found.append(f"SH-{m.group(1)}")
        stats['sh_marks'] = sorted(list(set(sh_found)), key=lambda x: int(re.search(r'\d+', x).group()))
        
        return stats, doc
    except Exception as e:
        return None, None

def analyze_drawing_with_ai(image_bytes, project_context=""):
    """Use Claude Vision API to analyze the drawing"""
    try:
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        prompt = f"""You are an expert plumbing engineer analyzing a plumbing floor plan drawing.

Analyze this DXF/CAD drawing and identify:

1. **Shaft/Bathroom Units**: Look for shaft labels (SH, SHAFT, S) and bathroom groupings
2. **Fixtures per shaft**: Count WC/toilet, wash basin/sink, floor drain/FD, kitchen sink, shower
3. **Drawing type**: Typical floor, ground floor, terrace, podium, etc.
4. **Pipe sizes visible**: 110mm, 75mm, 50mm networks
5. **Special observations**: Any unique plumbing configurations

For each shaft found, estimate fixture count based on visible symbols.

{f"Project context: {project_context}" if project_context else ""}

Return ONLY valid JSON:
{{
  "drawing_type": "Typical Floor Plan",
  "total_shafts": 0,
  "shafts": [
    {{
      "id": "SH-01",
      "bathroom_type": "Standard Toilet / Master Bathroom / Powder Room / Kitchen",
      "fixtures": {{
        "WC": 1,
        "Wash Basin": 1,
        "Floor Drain": 1,
        "Kitchen Sink": 0,
        "Shower": 0
      }},
      "notes": "Any special observations"
    }}
  ],
  "observations": "Overall drawing observations",
  "confidence": "High/Medium/Low",
  "pipe_sizes_visible": ["110mm", "50mm"]
}}"""

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 2000,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {"type": "text", "text": prompt}
                ]
            }]
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            text = data['content'][0]['text']
            
            # Parse JSON
            text = re.sub(r'```json|```', '', text).strip()
            return json.loads(text)
        else:
            return None
    except Exception as e:
        return None

def generate_boq_excel(sh_data, project_name="Huliot Project"):
    """Generate complete BOQ Excel from shaft data"""
    
    # Material database per fixture unit
    materials = [
        # 110mm WC system
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm L-3000mm Single Socket Pipe', 'unit': 'MTR', 'qty_per': 14.15, 'sku': '5751100300-i', 'price': 2461},
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm L-500mm Single Socket Pipe', 'unit': 'NOS.', 'qty_per': 2, 'sku': '5751100050-i', 'price': 452},
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm Socket', 'unit': 'NOS.', 'qty_per': 22, 'sku': '7071740275', 'price': 533},
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm 90 Bend', 'unit': 'NOS.', 'qty_per': 15, 'sku': '7070040870-i', 'price': 581},
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm 45 Bend', 'unit': 'NOS.', 'qty_per': 11, 'sku': '7070040470-i', 'price': 534},
        {'fixture': 'WC', 'desc': 'Huliot DIA.110mm Equal Tee', 'unit': 'NOS.', 'qty_per': 4, 'sku': '7071740675-i', 'price': 727},
        {'fixture': 'WC', 'desc': 'Huliot Dia.110mm Clamps (Fixed)', 'unit': 'NOS.', 'qty_per': 12, 'sku': '8011100', 'price': 234},
        {'fixture': 'WC', 'desc': 'Huliot Dia.110mm Clamps (Sliding)', 'unit': 'NOS.', 'qty_per': 6, 'sku': '8011101', 'price': 218},
        # 50mm Basin system
        {'fixture': 'Wash Basin', 'desc': 'Huliot DIA.50mm L-1000mm Single Socket Pipe', 'unit': 'MTR', 'qty_per': 5.8, 'sku': '5755000100-i', 'price': 390},
        {'fixture': 'Wash Basin', 'desc': 'Huliot DIA.50mm Socket', 'unit': 'NOS.', 'qty_per': 3, 'sku': '7071720275', 'price': 162},
        {'fixture': 'Wash Basin', 'desc': 'Huliot DIA.50mm 90 Bend', 'unit': 'NOS.', 'qty_per': 10, 'sku': '7070020870-i', 'price': 119},
        {'fixture': 'Wash Basin', 'desc': 'Huliot DIA.50mm 45 Bend', 'unit': 'NOS.', 'qty_per': 2, 'sku': '7070020470-i', 'price': 97},
        {'fixture': 'Wash Basin', 'desc': 'Huliot Dia.50mm Clamps (Fixed)', 'unit': 'NOS.', 'qty_per': 5, 'sku': '8010500', 'price': 118},
        {'fixture': 'Wash Basin', 'desc': 'Huliot Dia.50mm Clamps (Sliding)', 'unit': 'NOS.', 'qty_per': 2, 'sku': '8010501', 'price': 104},
        # 75mm Floor Drain system
        {'fixture': 'Floor Drain', 'desc': 'Huliot Floor Drain (Multi Floor Trap)', 'unit': 'NOS.', 'qty_per': 1, 'sku': '60117060', 'price': 1247},
        {'fixture': 'Floor Drain', 'desc': 'Huliot Floor Drain 150mm Height Riser', 'unit': 'NOS.', 'qty_per': 1, 'sku': '69201551 B-i', 'price': 542},
        {'fixture': 'Floor Drain', 'desc': 'Huliot DIA.75mm L-1000mm Single Socket Pipe', 'unit': 'MTR', 'qty_per': 3.0, 'sku': '5757500100-i', 'price': 620},
        {'fixture': 'Floor Drain', 'desc': 'Huliot DIA.75mm 90 Bend', 'unit': 'NOS.', 'qty_per': 2, 'sku': '7070030870-i', 'price': 284},
        # Kitchen Sink
        {'fixture': 'Kitchen Sink', 'desc': 'Huliot DIA.50mm L-1000mm Single Socket Pipe', 'unit': 'MTR', 'qty_per': 3.5, 'sku': '5755000100-i', 'price': 390},
        {'fixture': 'Kitchen Sink', 'desc': 'Huliot DIA.50mm 90 Bend', 'unit': 'NOS.', 'qty_per': 4, 'sku': '7070020870-i', 'price': 119},
        {'fixture': 'Kitchen Sink', 'desc': 'Huliot Dia.50mm Clamps', 'unit': 'NOS.', 'qty_per': 4, 'sku': '8010500', 'price': 118},
    ]
    
    rows = []
    sr = 1
    
    for mat in materials:
        fixture = mat['fixture']
        row = {
            'SR. NO.': sr,
            'DESCRIPTION': mat['desc'],
            'UNIT': mat['unit'],
            'SKU': mat['sku'],
            'Unit Price': mat['price'],
            'Discount': '35%'
        }
        
        for sh in sh_data:
            sh_id = sh['sh']
            count = sh['fixtures'].get(fixture, 0)
            qty = round(count * mat['qty_per'], 2) if count > 0 else ''
            row[sh_id] = qty
        
        total_qty = sum(
            sh['fixtures'].get(fixture, 0) * mat['qty_per']
            for sh in sh_data
        )
        row['Total QTY'] = round(total_qty, 2) if total_qty > 0 else 0
        row['Amount'] = round(total_qty * mat['price'] * 0.65, 2)
        
        rows.append(row)
        sr += 1
    
    df = pd.DataFrame(rows)
    
    # Write Excel
    temp_dir = tempfile.gettempdir()
    out_path = os.path.join(temp_dir, f"{project_name}_BOQ.xlsx")
    
    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='BOQ', index=False)
        
        # Summary
        total = df['Amount'].sum()
        summary = pd.DataFrame([
            {'Description': 'Project Name', 'Value': project_name},
            {'Description': 'Total Shafts', 'Value': len(sh_data)},
            {'Description': 'Total Line Items', 'Value': len(df)},
            {'Description': 'Sub Total (ex-tax)', 'Value': round(total, 2)},
            {'Description': 'GST 18%', 'Value': round(total * 0.18, 2)},
            {'Description': 'Grand Total', 'Value': round(total * 1.18, 2)},
        ])
        summary.to_excel(writer, sheet_name='Summary', index=False)
        
        # Shaft summary
        shaft_summary = pd.DataFrame([
            {
                'SH': sh['sh'],
                'Type': sh.get('type', 'Standard'),
                'WC': sh['fixtures'].get('WC', 0),
                'Wash Basin': sh['fixtures'].get('Wash Basin', 0),
                'Floor Drain': sh['fixtures'].get('Floor Drain', 0),
                'Kitchen Sink': sh['fixtures'].get('Kitchen Sink', 0),
            }
            for sh in sh_data
        ])
        shaft_summary.to_excel(writer, sheet_name='Shaft Summary', index=False)
    
    return df, out_path

# ─── HERO HEADER ─────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>HULIOT DIP</h1>
    <p>DRAWING INTELLIGENCE PLATFORM &nbsp;|&nbsp; DXF VIEWER &nbsp;+&nbsp; AI ANALYSIS &nbsp;+&nbsp; BOQ GENERATOR</p>
</div>
""", unsafe_allow_html=True)

# ─── SIDEBAR ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="section-title">PROJECT</div>', unsafe_allow_html=True)
    
    project_name = st.text_input("Project Name", "Huliot Project")
    consultant = st.text_input("Consultant", "")
    floors = st.number_input("Total Floors", 1, 50, 1)
    
    st.markdown("---")
    st.markdown('<div class="section-title">SETTINGS</div>', unsafe_allow_html=True)
    
    detection_radius = st.slider("SH Detection Radius (mm)", 500, 10000, 3000, 500)
    discount_pct = st.slider("Discount %", 0, 50, 35)
    include_tax = st.checkbox("Include 18% GST", True)
    
    st.markdown("---")
    st.markdown('<div class="section-title">LEGEND</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-family:'IBM Plex Mono',monospace; font-size:0.72rem; color:#8a8a7a; line-height:2;">
    🔴 WC &nbsp;|&nbsp; 110mm<br>
    🟡 Basin &nbsp;|&nbsp; 50mm<br>
    🟢 Floor Drain &nbsp;|&nbsp; 75mm<br>
    🔵 Kitchen &nbsp;|&nbsp; 50mm
    </div>
    """, unsafe_allow_html=True)

# ─── MAIN TABS ───────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📐 VIEWER", "🤖 AI ANALYSIS", "📊 BOQ", "📥 EXPORT"])

# ─── TAB 1: VIEWER ───────────────────────────────────────────────
with tab1:
    col_upload, col_info = st.columns([3, 1])
    
    with col_upload:
        st.markdown('<div class="section-title">UPLOAD DRAWING</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Upload DXF File",
            type=['dxf'],
            help="Upload DXF file. Export from AutoCAD: File > Save As > AutoCAD 2018 DXF"
        )
    
    if uploaded:
        # Save file
        temp_dir = tempfile.gettempdir()
        dxf_path = os.path.join(temp_dir, uploaded.name)
        with open(dxf_path, 'wb') as f:
            f.write(uploaded.getvalue())
        st.session_state.dxf_path = dxf_path
        
        # Get stats
        with st.spinner("Reading DXF..."):
            stats, doc = get_dxf_stats(dxf_path)
        
        if stats:
            st.session_state.dxf_doc = doc
            
            # Stats row
            cols = st.columns(5)
            stat_items = [
                ("ENTITIES", sum(stats['entities'].values())),
                ("LAYERS", len(stats['layers'])),
                ("BLOCKS", len(stats['blocks'])),
                ("TEXT ITEMS", len(stats['texts'])),
                ("SH MARKS", len(stats['sh_marks'])),
            ]
            for i, (lbl, val) in enumerate(stat_items):
                with cols[i]:
                    st.markdown(f"""
                    <div class="stat-card">
                        <div class="val">{val}</div>
                        <div class="lbl">{lbl}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # SH marks found
            if stats['sh_marks']:
                st.markdown(f'<span class="status-ok">✓ SH MARKS DETECTED: {" | ".join(stats["sh_marks"])}</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-warn">⚠ No SH marks found in text entities. Use AI Analysis to identify shafts manually.</span>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Render drawing
            st.markdown('<div class="section-title">DRAWING VIEW</div>', unsafe_allow_html=True)
            
            with st.spinner("Rendering drawing..."):
                img_bytes = render_dxf_to_image(dxf_path)
            
            if img_bytes:
                st.session_state.drawing_image = img_bytes
                st.image(img_bytes, use_container_width=True, caption=f"{uploaded.name}")
            else:
                st.warning("Could not render drawing. File may be too complex.")
            
            # Layer info
            with st.expander("📋 Layers & Blocks"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Layers:**")
                    for layer in stats['layers'][:20]:
                        st.code(layer, language='')
                with col2:
                    st.markdown("**Blocks:**")
                    for block in stats['blocks'][:20]:
                        st.code(block, language='')
        else:
            st.error("❌ Could not read DXF file. Ensure it's a valid DXF (not DWG).")
    else:
        st.markdown("""
        <div class="upload-zone">
            <h3 style="color:#1a5f3c; font-family:'Bebas Neue',sans-serif;">UPLOAD DXF TO BEGIN</h3>
            <p style="color:#8a8a7a; font-family:'IBM Plex Mono',monospace; font-size:0.8rem;">
            Export from AutoCAD: FILE → SAVE AS → AUTOCAD 2018 DXF
            </p>
        </div>
        """, unsafe_allow_html=True)

# ─── TAB 2: AI ANALYSIS ──────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-title">AI DRAWING ANALYSIS</div>', unsafe_allow_html=True)
    
    if not st.session_state.drawing_image:
        st.info("Upload and render a DXF first in the VIEWER tab.")
    else:
        st.image(st.session_state.drawing_image, use_container_width=True)
        
        context = st.text_input(
            "Project context (optional)",
            placeholder="e.g. Residential tower, typical floor, 4 bathrooms per floor"
        )
        
        col1, col2 = st.columns([2, 1])
        with col1:
            analyze_btn = st.button("🤖 Analyze Drawing with AI", type="primary", use_container_width=True)
        with col2:
            manual_btn = st.button("✏️ Enter Shafts Manually", use_container_width=True)
        
        if analyze_btn:
            with st.spinner("AI analyzing drawing..."):
                result = analyze_drawing_with_ai(st.session_state.drawing_image, context)
            
            if result:
                st.session_state.analysis_done = True
                
                st.markdown(f"""
                <div style="background:#0d1a12; border:1px solid #1a5f3c; border-radius:8px; padding:1rem; margin:1rem 0;">
                    <span style="color:#8a8a7a; font-family:'IBM Plex Mono',monospace; font-size:0.8rem;">
                    DRAWING TYPE: <b style="color:#00ff88">{result.get('drawing_type','Unknown')}</b> &nbsp;|&nbsp;
                    CONFIDENCE: <b style="color:#00ff88">{result.get('confidence','Medium')}</b> &nbsp;|&nbsp;
                    SHAFTS: <b style="color:#00ff88">{result.get('total_shafts', len(result.get('shafts',[])))}</b>
                    </span>
                </div>
                """, unsafe_allow_html=True)
                
                if result.get('observations'):
                    st.markdown(f"**Observations:** {result['observations']}")
                
                # Build SH data for BOQ
                sh_data = []
                for shaft in result.get('shafts', []):
                    sh_data.append({
                        'sh': shaft['id'],
                        'type': shaft.get('bathroom_type', 'Standard'),
                        'fixtures': shaft.get('fixtures', {'WC': 1, 'Wash Basin': 1, 'Floor Drain': 1}),
                        'notes': shaft.get('notes', '')
                    })
                
                st.session_state.sh_data = sh_data
                
                # Show shaft cards
                st.markdown('<div class="section-title">DETECTED SHAFTS</div>', unsafe_allow_html=True)
                
                for sh in sh_data:
                    fix = sh['fixtures']
                    st.markdown(f"""
                    <div class="sh-card">
                        <div class="sh-label">{sh['sh']}</div>
                        <div class="sh-type">{sh['type']}</div>
                        <div class="fixture-row">
                            <span class="fix-item">🔴 WC: {fix.get('WC',0)}</span>
                            <span class="fix-item">🟡 BASIN: {fix.get('Wash Basin',0)}</span>
                            <span class="fix-item">🟢 DRAIN: {fix.get('Floor Drain',0)}</span>
                            <span class="fix-item">🔵 KIT: {fix.get('Kitchen Sink',0)}</span>
                        </div>
                        {f'<div style="font-size:0.72rem; color:#8a8a7a; margin-top:0.5rem;">{sh["notes"]}</div>' if sh.get('notes') else ''}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.error("AI analysis failed. Use manual entry.")
        
        if manual_btn or (not st.session_state.analysis_done and not analyze_btn):
            st.markdown('<div class="section-title">MANUAL SHAFT ENTRY</div>', unsafe_allow_html=True)
            
            num_shafts = st.number_input("Number of Shafts (Bathrooms)", 1, 50, 4)
            
            sh_data_manual = []
            
            for i in range(int(num_shafts)):
                with st.expander(f"SH-{str(i+1).zfill(2)}", expanded=i < 3):
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    sh_id = col1.text_input("SH ID", f"SH-{str(i+1).zfill(2)}", key=f"sh_id_{i}")
                    wc = col2.number_input("WC", 0, 10, 1, key=f"wc_{i}")
                    basin = col3.number_input("Basin", 0, 10, 1, key=f"basin_{i}")
                    drain = col4.number_input("FD", 0, 10, 1, key=f"drain_{i}")
                    kitchen = col5.number_input("KIT", 0, 10, 0, key=f"kit_{i}")
                    
                    sh_data_manual.append({
                        'sh': sh_id,
                        'type': 'Standard',
                        'fixtures': {
                            'WC': wc,
                            'Wash Basin': basin,
                            'Floor Drain': drain,
                            'Kitchen Sink': kitchen
                        }
                    })
            
            if st.button("✅ Confirm Shafts", type="primary", use_container_width=True):
                st.session_state.sh_data = sh_data_manual
                st.success(f"✅ {num_shafts} shafts configured")

# ─── TAB 3: BOQ ──────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="section-title">BILL OF QUANTITIES</div>', unsafe_allow_html=True)
    
    if not st.session_state.sh_data:
        st.info("Complete AI Analysis or enter shafts manually first.")
    else:
        # Summary cards
        sh_data = st.session_state.sh_data
        
        col1, col2, col3, col4 = st.columns(4)
        
        total_wc = sum(s['fixtures'].get('WC', 0) for s in sh_data)
        total_basin = sum(s['fixtures'].get('Wash Basin', 0) for s in sh_data)
        total_drain = sum(s['fixtures'].get('Floor Drain', 0) for s in sh_data)
        
        metrics = [
            ("SHAFTS", len(sh_data)),
            ("TOTAL WC", total_wc),
            ("TOTAL BASINS", total_basin),
            ("TOTAL DRAINS", total_drain)
        ]
        
        for col, (lbl, val) in zip([col1, col2, col3, col4], metrics):
            with col:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="val">{val}</div>
                    <div class="lbl">{lbl}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Generate BOQ
        if st.button("📊 Generate BOQ", type="primary", use_container_width=True):
            with st.spinner("Generating BOQ..."):
                df, boq_path = generate_boq_excel(sh_data, project_name)
            
            st.session_state.boq_df = df
            st.session_state.boq_path = boq_path
            
            total_amount = df['Amount'].sum()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"""<div class="stat-card">
                    <div class="val">{len(df)}</div>
                    <div class="lbl">LINE ITEMS</div>
                </div>""", unsafe_allow_html=True)
            with col2:
                st.markdown(f"""<div class="stat-card">
                    <div class="val">₹{total_amount/100000:.1f}L</div>
                    <div class="lbl">SUB TOTAL</div>
                </div>""", unsafe_allow_html=True)
            with col3:
                st.markdown(f"""<div class="stat-card">
                    <div class="val">₹{total_amount*1.18/100000:.1f}L</div>
                    <div class="lbl">GRAND TOTAL</div>
                </div>""", unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown('<div class="section-title">BOQ PREVIEW</div>', unsafe_allow_html=True)
            st.dataframe(df, use_container_width=True, height=400)

# ─── TAB 4: EXPORT ───────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-title">EXPORT FILES</div>', unsafe_allow_html=True)
    
    if st.session_state.boq_df is None:
        st.info("Generate BOQ in the BOQ tab first.")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 BOQ Excel")
            st.markdown(f"""
            <div class="sh-card">
                <div style="font-family:'IBM Plex Mono',monospace; font-size:0.8rem; color:#b0c0b0;">
                    <b>Project:</b> {project_name}<br>
                    <b>Shafts:</b> {len(st.session_state.sh_data)}<br>
                    <b>Items:</b> {len(st.session_state.boq_df)}<br>
                    <b>Sheets:</b> BOQ / Summary / Shaft Summary
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            with open(st.session_state.boq_path, 'rb') as f:
                st.download_button(
                    "⬇️ Download BOQ Excel",
                    f.read(),
                    file_name=f"{project_name}_BOQ.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        
        with col2:
            st.markdown("### 📐 Marked DXF")
            st.markdown(f"""
            <div class="sh-card">
                <div style="font-family:'IBM Plex Mono',monospace; font-size:0.8rem; color:#b0c0b0;">
                    Original DXF with SH labels added<br>
                    (if DXF was uploaded)
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.dxf_path:
                with open(st.session_state.dxf_path, 'rb') as f:
                    st.download_button(
                        "⬇️ Download DXF",
                        f.read(),
                        file_name=f"{project_name}_marked.dxf",
                        mime="application/dxf",
                        use_container_width=True
                    )

# ─── FOOTER ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style="text-align:center; padding:1rem 0; font-family:'IBM Plex Mono',monospace; font-size:0.72rem; color:#8a8a7a;">
    HULIOT DRAWING INTELLIGENCE PLATFORM v3.0 &nbsp;|&nbsp; 
    AI-POWERED PLUMBING BOQ &nbsp;|&nbsp; 
    HULIOT PIPES & FITTINGS PVT. LTD.
</div>
""", unsafe_allow_html=True)
