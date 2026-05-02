# cad_qty_app.py
import streamlit as st
from extract_qty import extract, export_excel
import tempfile

st.title("Huliot CAD Quantity Extractor")

dxf = st.file_uploader("Upload DXF", type=['dxf'])
scale = st.number_input("Drawing scale (1:X)", value=100)

if dxf and st.button("Extract"):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dxf') as tmp:
        tmp.write(dxf.read())
        result = extract(tmp.name, scale)
        
    st.write(f"**Total fittings:** {result['total_fittings']}")
    
    # Show table
    for b in result['blocks']:
        st.write(f"{b['type']} {b['size']} — {b['qty']}×")
    
    # Download Excel
    xl_path = export_excel(result, '/tmp/boq.xlsx')
    with open(xl_path, 'rb') as f:
        st.download_button("⬇️ Download BOQ", f, "quantity_takeoff.xlsx")
