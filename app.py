import streamlit as st
import pandas as pd
import ezdxf
import io
import base64
from pathlib import Path
from collections import defaultdict, Counter
import re
import math
import tempfile
import os

st.set_page_config(page_title="Huliot Auto SH Marker + BOQ", layout="wide")

# CSS
st.markdown("""
<style>
.big-font {font-size:24px !important; font-weight:bold; color:#1a5f3c;}
.metric-green {background:#1a5f3c; color:white; padding:20px; border-radius:10px; text-align:center;}
.step-box {background:#f0f8f4; border-left:5px solid #1a5f3c; padding:15px; margin:10px 0;}
</style>
""", unsafe_allow_html=True)

st.markdown('<p class="big-font">🚿 Huliot Drawing Marker + BOQ Generator</p>', unsafe_allow_html=True)
st.markdown("**Upload DXF → AI marks bathrooms with SH → Download marked DXF + BOQ Excel**")

# Session state
if 'bathrooms' not in st.session_state:
    st.session_state.bathrooms = []
if 'marked_dxf_path' not in st.session_state:
    st.session_state.marked_dxf_path = None

def distance(p1, p2):
    """Euclidean distance"""
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def detect_bathrooms_spatial_clustering(dxf_path, grid_size=5000):
    """Detect bathrooms by clustering WC blocks spatially"""
    try:
        if not os.path.exists(dxf_path):
            st.error(f"❌ File not found: {dxf_path}")
            return []
        
        file_size = os.path.getsize(dxf_path)
        if file_size < 100:
            st.error("❌ File too small - invalid DXF")
            return []
        
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
    except Exception as e:
        error_msg = str(e)
        st.error(f"❌ Cannot read DXF file")
        return []
    
    wc_blocks = []
    basin_blocks = []
    drain_blocks = []
    
    try:
        for entity in msp.query('INSERT'):
            name = entity.dxf.name.lower()
            pos = (entity.dxf.insert.x, entity.dxf.insert.y)
            
            # NOTE: If detection still fails, add your specific block names inside these brackets!
            if re.search(r'(wc|toilet|closet|ewc)', name):
                wc_blocks.append(pos)
            elif re.search(r'(basin|sink|wash|lav)', name):
                basin_blocks.append(pos)
            elif re.search(r'(drain|fd|gully)', name):
                drain_blocks.append(pos)
    except Exception as e:
        st.warning(f"Could not parse blocks: {str(e)[:50]}")
    
    if not wc_blocks:
        return []
    
    bathrooms = []
    used_wcs = set()
    
    for i, wc_pos in enumerate(wc_blocks):
        if i in used_wcs:
            continue
            
        nearby_basins = sum(1 for b in basin_blocks if distance(wc_pos, b) < grid_size)
        nearby_drains = sum(1 for d in drain_blocks if distance(wc_pos, d) < grid_size)
        nearby_wcs = sum(1 for j, w in enumerate(wc_blocks) if j != i and distance(wc_pos, w) < grid_size)
        
        bathroom = {
            'center': wc_pos,
            'fixtures': {
                'WC': 1 + nearby_wcs,
                'Wash Basin': nearby_basins,
                'Floor Drain': nearby_drains
            }
        }
        
        bathrooms.append(bathroom)
        used_wcs.add(i)
    
    return bathrooms

def convert_dwg_to_dxf_advanced(dwg_path):
    dxf_path = dwg_path.replace('.dwg', '_converted.dxf').replace('.DWG', '_converted.dxf')
    try:
        doc = ezdxf.readfile(dwg_path)
        doc.saveas(dxf_path)
        return dxf_path
    except Exception:
        pass
    return None

def detect_existing_sh_marks(dxf_path):
    """Check if DXF already has SH-XX marks"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        sh_marks = []
        
        # Look for TEXT entities with SH pattern
        for entity in msp.query('TEXT MTEXT'):
            if hasattr(entity, 'dxf'):
                try:
                    text_content = entity.dxf.text if hasattr(entity.dxf, 'text') else str(entity)
                    
                    # FIXED REGEX: Now matches "SH-12" or "SH12"
                    match = re.search(r'SH-?(\d+)', text_content, re.IGNORECASE)
                    if match:
                        sh_num = match.group(1)
                        pos = (entity.dxf.insert.x, entity.dxf.insert.y) if hasattr(entity.dxf, 'insert') else (0, 0)
                        sh_marks.append({
                            'sh': f"SH-{sh_num}",
                            'text': text_content,
                            'position': pos
                        })
                except:
                    pass
        return sh_marks
    except:
        return []

def extract_fixtures_from_sh(dxf_path, sh_marks):
    """Extract fixture counts around existing SH marks"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        wc_blocks = []
        basin_blocks = []
        drain_blocks = []
        
        for entity in msp.query('INSERT'):
            name = entity.dxf.name.lower()
            pos = (entity.dxf.insert.x, entity.dxf.insert.y)
            
            # NOTE: If detection still fails, add your specific block names inside these brackets!
            if re.search(r'(wc|toilet|closet|ewc|water)', name):
                wc_blocks.append(pos)
            elif re.search(r'(basin|sink|wash|lav)', name):
                basin_blocks.append(pos)
            elif re.search(r'(drain|fd|gully|mft)', name):
                drain_blocks.append(pos)
        
        bathrooms = []
        radius = 3000  # Search radius around SH mark
        
        for sh_mark in sh_marks:
            sh_pos = sh_mark['position']
            
            wc_count = sum(1 for w in wc_blocks if distance(sh_pos, w) < radius)
            basin_count = sum(1 for b in basin_blocks if distance(sh_pos, b) < radius)
            drain_count = sum(1 for d in drain_blocks if distance(sh_pos, d) < radius)
            
            bathroom = {
                'sh': sh_mark['sh'],
                'center': sh_pos,
                'fixtures': {
                    'WC': max(wc_count, 1),
                    'Wash Basin': basin_count,
                    'Floor Drain': drain_count
                }
            }
            bathrooms.append(bathroom)
        
        return bathrooms
    except:
        return []

def inspect_dxf_contents(dxf_path):
    """Inspect DXF file and show what's inside"""
    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        
        entity_types = {}
        block_names = set()
        layer_names = set()
        
        for entity in msp:
            etype = entity.dxftype()
            entity_types[etype] = entity_types.get(etype, 0) + 1
            
            if etype == 'INSERT':
                block_names.add(entity.dxf.name.lower())
            
            if hasattr(entity.dxf, 'layer'):
                layer_names.add(entity.dxf.layer)
        
        return {
            'entity_types': entity_types,
            'block_names': sorted(list(block_names)),
            'layer_names': sorted(list(layer_names)),
            'total_entities': len(list(msp))
        }
    except Exception as e:
        return {'error': str(e)}

def inspect_and_show(dxf_path):
    """Show DXF inspection results to user"""
    info = inspect_dxf_contents(dxf_path)
    
    if 'error' in info:
        st.error(f"Cannot inspect: {info['error']}")
        return None
    
    st.markdown("### 🔍 DXF File Contents Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Entities", info['total_entities'])
    with col2:
        st.metric("Unique Blocks", len(info['block_names']))
    with col3:
        st.metric("Unique Layers", len(info['layer_names']))
    
    st.markdown("---")
    st.markdown("**Entity Types Found:**")
    entity_col1, entity_col2 = st.columns(2)
    with entity_col1:
        for etype in sorted(info['entity_types'].keys())[:5]:
            count = info['entity_types'][etype]
            st.write(f"• {etype}: **{count}**")
    with entity_col2:
        for etype in sorted(info['entity_types'].keys())[5:]:
            count = info['entity_types'][etype]
            st.write(f"• {etype}: **{count}**")
    
    st.markdown("---")
    if info['block_names']:
        st.markdown("**Block Names Found (first 30):**")
        block_display = info['block_names'][:30]
        blocks_text = "\n".join(block_display)
        st.code(blocks_text, language='')
        
        if len(info['block_names']) > 30:
            st.info(f"... and {len(info['block_names']) - 30} more blocks")
    else:
        st.warning("⚠️ No blocks found in file")
    
    return info

def add_sh_labels_to_dxf(input_dxf, output_dxf, bathrooms, prefix="SH"):
    """Add SH text labels to DXF at bathroom centers"""
    doc = ezdxf.readfile(input_dxf)
    msp = doc.modelspace()
    
    for i, bathroom in enumerate(bathrooms):
        sh_num = f"{prefix}-{str(i+1).zfill(2)}"
        center = bathroom['center']
        
        msp.add_text(
            sh_num,
            dxfattribs={
                'insert': (center[0], center[1], 0),
                'height': 500,
                'color': 1,
                'layer': 'SH_LABELS',
                'style': 'Standard'
            }
        )
        msp.add_circle(
            center=(center[0], center[1], 0),
            radius=800,
            dxfattribs={'color': 1, 'layer': 'SH_LABELS'}
        )
        bathroom['sh'] = sh_num
    
    doc.saveas(output_dxf)
    return bathrooms

def generate_boq_excel(bathrooms, output_path, project_name=""):
    """Generate BOQ Excel matching Huliot template format"""
    materials_db = {
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
    
    rows = []
    sr = 1
    
    for fixture_type, materials in materials_db.items():
        for material in materials:
            row = {
                'SR. NO.': sr,
                'DESCRIPTION': material['desc'],
                'UNIT': material['unit']
            }
            for bathroom in bathrooms:
                sh = bathroom['sh']
                fixture_count = bathroom['fixtures'].get(fixture_type, 0)
                qty = round(fixture_count * material['qty'], 2)
                row[sh] = qty if qty > 0 else ''
            
            total_qty = sum(bathroom['fixtures'].get(fixture_type, 0) * material['qty'] for bathroom in bathrooms)
            row['Total QTY'] = round(total_qty, 2)
            row['SKU'] = material['sku']
            row['Unit Price'] = material['price']
            row['Discount'] = '35%'
            row['Total'] = round(total_qty * material['price'] * 0.65, 2)
            rows.append(row)
            sr += 1
            
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Typical Floor BOQ', index=False)
        summary = pd.DataFrame([
            {'Item': 'Project Name', 'Value': project_name},
            {'Item': 'Total Bathrooms', 'Value': len(bathrooms)},
            {'Item': 'Total Items', 'Value': len(rows)},
            {'Item': 'Sub Total', 'Value': df['Total'].sum()},
            {'Item': 'Tax (18%)', 'Value': df['Total'].sum() * 0.18},
            {'Item': 'Grand Total', 'Value': df['Total'].sum() * 1.18}
        ])
        summary.to_excel(writer, sheet_name='Summary', index=False)
    
    return df

# UI
tab1, tab2, tab3 = st.tabs(["📤 Upload & Process", "🎯 Review SH Marks", "💾 Download"])

with tab1:
    st.markdown('<div class="step-box">Upload DXF → Auto detect → Mark SH → Generate BOQ</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload DWG or DXF Drawing", type=['dxf', 'dwg'], accept_multiple_files=True)
    
    col1, col2 = st.columns(2)
    with col1:
        sh_prefix = st.text_input("SH Prefix", "SH")
    with col2:
        grid_size = st.number_input("Detection Radius (mm)", 1000, 10000, 5000, 500)
    
    if uploaded:
        st.markdown(f"### 📁 Processing {len(uploaded)} file(s)")
        progress_bar = st.progress(0)
        
        for file_idx, uploaded_file in enumerate(uploaded):
            progress = (file_idx + 1) / len(uploaded)
            progress_bar.progress(progress)
            
            is_dwg = uploaded_file.name.lower().endswith('.dwg')
            temp_dir = tempfile.gettempdir()
            input_path = os.path.join(temp_dir, f"input_{uploaded_file.name}")
            
            with open(input_path, 'wb') as f:
                f.write(uploaded_file.getvalue())
            
            st.info(f"**{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
            
            if is_dwg:
                st.write("🔄 Converting DWG to DXF...")
                with st.spinner("Trying multiple conversion methods..."):
                    dxf_path = convert_dwg_to_dxf_advanced(input_path)
                if dxf_path:
                    st.success("✅ DWG converted to DXF")
                    process_path = dxf_path
                else:
                    st.error("❌ Cannot convert DWG. Please upload DXF.")
                    st.stop()
            else:
                process_path = input_path
            
            if st.button(f"🔍 Detect & Mark {uploaded_file.name}", type="primary", use_container_width=True):
                with st.spinner(f"Analyzing {uploaded_file.name}..."):
                    existing_sh = detect_existing_sh_marks(process_path)
                    
                    if existing_sh:
                        st.success(f"✅ Found {len(existing_sh)} existing SH marks in drawing")
                        st.info(f"Marks: {', '.join([sh['sh'] for sh in existing_sh])}")
                        
                        bathrooms = extract_fixtures_from_sh(process_path, existing_sh)
                        if bathrooms:
                            st.success(f"✅ Extracted fixtures for {len(bathrooms)} shafts")
                            st.session_state.bathrooms = bathrooms
                            st.session_state.marked_dxf_path = process_path
                        else:
                            st.warning("⚠️ Could not extract fixtures from marks. Automatically inspecting file...")
                            
                            # Auto-inspect if fixtures are missing!
                            inspect_info = inspect_and_show(process_path)
                            if inspect_info and 'block_names' in inspect_info:
                                st.markdown("""
                                ### 💡 Next Steps:
                                Look at the **Block Names Found** above. Find the names of your WC and Basin blocks and share them here or add them to the regex logic in the code!
                                """)
                    else:
                        st.info("No existing SH marks found. Running auto-detection...")
                        bathrooms = detect_bathrooms_spatial_clustering(process_path, grid_size)
                        
                        if not bathrooms:
                            st.error(f"❌ No bathrooms detected in {uploaded_file.name}")
                            st.info("💡 Automatically inspecting the file to find your block names...")
                            
                            # AUTO-INSPECT HAPPENS HERE (No nested button)
                            inspect_info = inspect_and_show(process_path)
                            
                            if inspect_info and 'block_names' in inspect_info:
                                st.markdown("""
                                ### 💡 Next Steps:
                                Look at the **Block Names Found** above. Find the names of your WC and Basin blocks and share them here!
                                """)
                        else:
                            st.success(f"✅ Found {len(bathrooms)} bathrooms in {uploaded_file.name}")
                            marked_path = os.path.join(temp_dir, f"marked_{uploaded_file.name.replace('.dwg', '.dxf').replace('.DWG', '.dxf')}")
                            bathrooms = add_sh_labels_to_dxf(process_path, marked_path, bathrooms, sh_prefix)
                            st.session_state.bathrooms = bathrooms
                            st.session_state.marked_dxf_path = marked_path
                            st.success(f"✅ Added SH labels to {uploaded_file.name}")

            st.divider()

with tab2:
    if st.session_state.bathrooms:
        st.markdown("### 🎯 Detected Bathrooms with SH Labels")
        cols = st.columns(min(len(st.session_state.bathrooms), 4))
        
        for i, bathroom in enumerate(st.session_state.bathrooms):
            with cols[i % 4]:
                st.markdown(f"**{bathroom['sh']}**")
                st.metric("WC", bathroom['fixtures'].get('WC', 0))
                st.metric("Basin", bathroom['fixtures'].get('Wash Basin', 0))
                st.metric("FD", bathroom['fixtures'].get('Floor Drain', 0))
        
        st.markdown("---")
        
        if st.button("📊 Generate BOQ Preview"):
            temp_dir = tempfile.gettempdir()
            boq_path = os.path.join(temp_dir, "preview_boq.xlsx")
            df = generate_boq_excel(st.session_state.bathrooms, boq_path)
            
            st.dataframe(df.head(20), use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown('<div class="metric-green"><h3>Total Items</h3><h2>' + str(len(df)) + '</h2></div>', unsafe_allow_html=True)
            with col2:
                total = df['Total'].sum()
                st.markdown(f'<div class="metric-green"><h3>Sub Total</h3><h2>₹{total/100000:.1f}L</h2></div>', unsafe_allow_html=True)
            with col3:
                grand = total * 1.18
                st.markdown(f'<div class="metric-green"><h3>Grand Total</h3><h2>₹{grand/100000:.1f}L</h2></div>', unsafe_allow_html=True)
    else:
        st.info("No bathrooms detected yet. Upload DXF and detect first.")

with tab3:
    if st.session_state.marked_dxf_path and st.session_state.bathrooms:
        st.markdown("### 💾 Download Files")
        project_name = st.text_input("Project Name", "Huliot_Project")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**📐 Marked DXF Drawing**")
            with open(st.session_state.marked_dxf_path, 'rb') as f:
                st.download_button("⬇️ Download Marked DXF", f.read(), file_name=f"{project_name}_marked.dxf", mime="application/dxf")
        
        with col2:
            st.markdown("**📊 BOQ Excel**")
            temp_dir = tempfile.gettempdir()
            boq_path = os.path.join(temp_dir, f"{project_name}_BOQ.xlsx")
            generate_boq_excel(st.session_state.bathrooms, boq_path, project_name)
            
            with open(boq_path, 'rb') as f:
                st.download_button("⬇️ Download BOQ Excel", f.read(), file_name=f"{project_name}_BOQ.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("Process drawing first to generate files")
