"""
Huliot BOQ Generator - SIMPLE VERSION
Detect SH marks in drawing → Count fixtures → Generate BOQ
"""

import streamlit as st
import pandas as pd
import ezdxf
import os
import tempfile
import re
import math

st.set_page_config(page_title="Huliot BOQ Generator", layout="wide")

# CSS
st.markdown("""
<style>
.main-title {font-size:2.5rem; font-weight:700; color:#1a5f3c; margin-bottom:0.5rem;}
.subtitle {font-size:1.1rem; color:#666; margin-bottom:2rem;}
.success-box {background:#d4edda; border:1px solid #c3e6cb; color:#155724; padding:1rem; border-radius:4px; margin:1rem 0;}
.info-box {background:#e7f3ff; border:1px solid #b3d9ff; color:#004085; padding:1rem; border-radius:4px; margin:1rem 0;}
.metric-card {background:#1a5f3c; color:white; padding:1.5rem; border-radius:10px; text-align:center; margin:0.5rem;}
</style>
""", unsafe_allow_html=True)

st.markdown('<h1 class="main-title">🚿 Huliot BOQ Generator</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Mark SH in AutoCAD → Upload DXF → Get BOQ</p>', unsafe_allow_html=True)

# Initialize session state
if 'sh_marks' not in st.session_state:
    st.session_state.sh_marks = []
if 'boq_data' not in st.session_state:
    st.session_state.boq_data = None

def distance(p1, p2):
    """Calculate distance between two points"""
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def find_sh_marks(dxf_path):
    """Find all SH-XX text marks in DXF"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        sh_marks = []
        
        # Find TEXT entities with SH pattern
        for entity in msp.query('TEXT MTEXT'):
            try:
                text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else str(entity)
                pos = (entity.dxf.insert.x, entity.dxf.insert.y) if hasattr(entity.dxf, 'insert') else (0, 0)
                
                # Match SH-XX pattern (case-insensitive)
                match = re.search(r'SH-(\d+)', text_content, re.IGNORECASE)
                if match:
                    sh_num = match.group(1)
                    sh_marks.append({
                        'sh': f"SH-{sh_num}",
                        'position': pos,
                        'text': text_content
                    })
            except:
                pass
        
        return sorted(sh_marks, key=lambda x: int(re.search(r'\d+', x['sh']).group()))
    
    except Exception as e:
        return []

def count_fixtures_around_sh(dxf_path, sh_marks, radius=3000):
    """Count fixtures (WC, basin, drain) around each SH mark"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        bathrooms = []
        
        # Find all fixture blocks
        wc_blocks = []
        basin_blocks = []
        drain_blocks = []
        
        for entity in msp.query('INSERT'):
            try:
                name = entity.dxf.name.lower()
                pos = (entity.dxf.insert.x, entity.dxf.insert.y)
                
                if any(x in name for x in ['wc', 'toilet', 'closet', 'water']):
                    wc_blocks.append(pos)
                elif any(x in name for x in ['basin', 'sink', 'wash', 'lav']):
                    basin_blocks.append(pos)
                elif any(x in name for x in ['drain', 'fd', 'gully', 'trap', 'mft']):
                    drain_blocks.append(pos)
            except:
                pass
        
        # Count fixtures per SH
        for sh in sh_marks:
            pos = sh['position']
            
            wc_count = sum(1 for w in wc_blocks if distance(pos, w) < radius)
            basin_count = sum(1 for b in basin_blocks if distance(pos, b) < radius)
            drain_count = sum(1 for d in drain_blocks if distance(pos, d) < radius)
            
            bathrooms.append({
                'sh': sh['sh'],
                'position': pos,
                'fixtures': {
                    'WC': max(wc_count, 1) if wc_count > 0 else 1,
                    'Wash Basin': basin_count if basin_count > 0 else 1,
                    'Floor Drain': drain_count if drain_count > 0 else 1
                }
            })
        
        return bathrooms
    except:
        return []

def generate_boq_excel(bathrooms, output_path, project_name="Huliot Project"):
    """Generate BOQ Excel file"""
    
    # Material rates per fixture
    materials = {
        'WC': [
            {'desc': 'Huliot DIA.110mm L-3000mm Single Socket Pipe', 'unit': 'MTR', 'qty': 14.15, 'sku': '5751100300-i', 'price': 2461},
            {'desc': 'Huliot DIA.110mm Socket', 'unit': 'NOS.', 'qty': 22, 'sku': '7071740275', 'price': 533},
            {'desc': 'Huliot DIA.110mm 90 Bend', 'unit': 'NOS.', 'qty': 15, 'sku': '7070040870-i', 'price': 581},
            {'desc': 'Huliot DIA.110mm 45 Bend', 'unit': 'NOS.', 'qty': 11, 'sku': '7070040470-i', 'price': 534},
            {'desc': 'Huliot DIA.110mm Tee', 'unit': 'NOS.', 'qty': 4, 'sku': '7071740675-i', 'price': 727},
            {'desc': 'Huliot Dia.110mm Clamps', 'unit': 'NOS.', 'qty': 18, 'sku': '8011100', 'price': 234},
        ],
        'Wash Basin': [
            {'desc': 'Huliot DIA.50mm L-1000mm Single Socket Pipe', 'unit': 'MTR', 'qty': 5.8, 'sku': '5755000100-i', 'price': 390},
            {'desc': 'Huliot DIA.50mm Socket', 'unit': 'NOS.', 'qty': 3, 'sku': '7071720275', 'price': 162},
            {'desc': 'Huliot DIA.50mm 90 Bend', 'unit': 'NOS.', 'qty': 10, 'sku': '7070020870-i', 'price': 119},
            {'desc': 'Huliot DIA.50mm 45 Bend', 'unit': 'NOS.', 'qty': 2, 'sku': '7070020470-i', 'price': 97},
            {'desc': 'Huliot Dia.50mm Clamps', 'unit': 'NOS.', 'qty': 7, 'sku': '8010500', 'price': 118},
        ],
        'Floor Drain': [
            {'desc': 'Huliot Floor Drain (Multi Floor Trap)', 'unit': 'NOS.', 'qty': 1, 'sku': '60117060', 'price': 1247},
            {'desc': 'Huliot Floor Drain 150mm Height Riser', 'unit': 'NOS.', 'qty': 1, 'sku': '69201551 B-i', 'price': 542},
        ]
    }
    
    # Build rows
    rows = []
    sr = 1
    
    for fixture_type, items in materials.items():
        for item in items:
            row = {
                'SR. NO.': sr,
                'DESCRIPTION': item['desc'],
                'UNIT': item['unit']
            }
            
            # Quantity per SH
            for bathroom in bathrooms:
                sh = bathroom['sh']
                fixture_count = bathroom['fixtures'].get(fixture_type, 0)
                qty = round(fixture_count * item['qty'], 2)
                row[sh] = qty if qty > 0 else ''
            
            # Totals
            total_qty = sum(bathroom['fixtures'].get(fixture_type, 0) * item['qty'] for bathroom in bathrooms)
            row['Total QTY'] = round(total_qty, 2) if total_qty > 0 else 0
            row['SKU'] = item['sku']
            row['Unit Price'] = item['price']
            row['Discount'] = '35%'
            row['Amount'] = round(total_qty * item['price'] * 0.65, 2)
            
            rows.append(row)
            sr += 1
    
    df = pd.DataFrame(rows)
    
    # Write Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='BOQ', index=False)
        
        # Summary sheet
        total_amount = df['Amount'].sum()
        summary_data = {
            'Item': [
                'Project Name',
                'Total Bathrooms',
                'Total Line Items',
                'Sub Total',
                'Tax (18%)',
                'Grand Total'
            ],
            'Value': [
                project_name,
                len(bathrooms),
                len(rows),
                round(total_amount, 2),
                round(total_amount * 0.18, 2),
                round(total_amount * 1.18, 2)
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    return df

# Main UI
tab1, tab2, tab3 = st.tabs(["📤 Upload", "🎯 SH Marks", "💾 BOQ"])

with tab1:
    st.markdown('<div class="info-box"><b>Step 1:</b> Upload DXF with SH marks</div>', unsafe_allow_html=True)
    
    st.markdown("### Before uploading, ensure your DXF has:")
    st.write("✓ SH-01, SH-02... text marks at each bathroom location")
    st.write("✓ Fixture blocks (WC, basin, drain)")
    st.write("✓ Saved as DXF format")
    
    uploaded_file = st.file_uploader("Upload DXF File", type=['dxf'])
    
    if uploaded_file:
        # Save file
        temp_dir = tempfile.gettempdir()
        dxf_path = os.path.join(temp_dir, uploaded_file.name)
        
        with open(dxf_path, 'wb') as f:
            f.write(uploaded_file.getvalue())
        
        st.success(f"✅ {uploaded_file.name} uploaded ({uploaded_file.size / 1024 / 1024:.1f} MB)")
        
        # Find SH marks
        if st.button("🔍 Find SH Marks", type="primary", use_container_width=True):
            with st.spinner("Scanning for SH marks..."):
                sh_marks = find_sh_marks(dxf_path)
            
            if sh_marks:
                st.session_state.sh_marks = sh_marks
                st.session_state.dxf_path = dxf_path
                st.success(f"✅ Found {len(sh_marks)} SH marks")
                st.info(f"Marks: {', '.join([m['sh'] for m in sh_marks])}")
            else:
                st.error("❌ No SH marks found in file")
                st.warning("**Action:** Add SH-01, SH-02... text marks in AutoCAD before uploading")

with tab2:
    if st.session_state.sh_marks:
        st.markdown('<div class="info-box"><b>Step 2:</b> Review detected SH marks</div>', unsafe_allow_html=True)
        
        # Show SH marks
        st.markdown("### 📍 SH Marks Found")
        
        cols = st.columns(min(len(st.session_state.sh_marks), 5))
        for i, sh in enumerate(st.session_state.sh_marks):
            with cols[i % 5]:
                st.markdown(f"**{sh['sh']}**")
                st.caption(f"Position: ({sh['position'][0]:.0f}, {sh['position'][1]:.0f})")
        
        st.markdown("---")
        
        # Count fixtures
        if st.button("📊 Count Fixtures Around SH", type="primary", use_container_width=True):
            with st.spinner("Counting fixtures..."):
                bathrooms = count_fixtures_around_sh(st.session_state.dxf_path, st.session_state.sh_marks)
            
            if bathrooms:
                st.session_state.bathrooms = bathrooms
                st.success(f"✅ Fixtures counted for {len(bathrooms)} shafts")
                
                # Show summary
                st.markdown("### 🚿 Fixture Summary")
                summary_data = []
                for b in bathrooms:
                    summary_data.append({
                        'SH': b['sh'],
                        'WC': b['fixtures'].get('WC', 0),
                        'Basin': b['fixtures'].get('Wash Basin', 0),
                        'Drain': b['fixtures'].get('Floor Drain', 0)
                    })
                
                df_summary = pd.DataFrame(summary_data)
                st.dataframe(df_summary, use_container_width=True)
            else:
                st.error("❌ Could not count fixtures")
    else:
        st.info("📤 Upload DXF and find SH marks first")

with tab3:
    if 'bathrooms' in st.session_state and st.session_state.bathrooms:
        st.markdown('<div class="info-box"><b>Step 3:</b> Generate and download BOQ</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            project_name = st.text_input("Project Name", "Huliot Project")
        with col2:
            st.write("")
            st.write("")
        
        if st.button("📋 Generate BOQ Excel", type="primary", use_container_width=True):
            temp_dir = tempfile.gettempdir()
            boq_path = os.path.join(temp_dir, f"{project_name}_BOQ.xlsx")
            
            with st.spinner("Generating BOQ..."):
                df = generate_boq_excel(st.session_state.bathrooms, boq_path, project_name)
            
            st.success("✅ BOQ generated successfully!")
            
            # Show preview
            st.markdown("### 📊 BOQ Preview (first 10 rows)")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Metrics
            total_amount = df['Amount'].sum()
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f'<div class="metric-card"><h4>Items</h4><h2>{len(df)}</h2></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="metric-card"><h4>Sub Total</h4><h2>₹{total_amount/100000:.1f}L</h2></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="metric-card"><h4>Grand Total</h4><h2>₹{total_amount*1.18/100000:.1f}L</h2></div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Download button
            with open(boq_path, 'rb') as f:
                st.download_button(
                    "⬇️ Download BOQ Excel",
                    f.read(),
                    file_name=f"{project_name}_BOQ.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    else:
        st.info("🎯 Find SH marks and count fixtures first")

st.markdown("---")
st.markdown("<p style='text-align:center; color:#666;'><b>Huliot BOQ Generator v2.0</b> | Simple & Reliable</p>", unsafe_allow_html=True)
