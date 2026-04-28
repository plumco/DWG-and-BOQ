# Huliot AutoBOQ Generator

## What It Does

**Complete automation pipeline:**

1. Upload DXF drawing (NO SH labels needed)
2. AI detects bathrooms by clustering WC/basin/drain blocks
3. **Modifies DXF** - adds SH-01, SH-02... text labels at bathroom centers
4. Generates BOQ Excel matching your template format
5. Download marked DXF + BOQ Excel

## Quick Start

### Deploy to Streamlit Cloud (Free)

1. **Create GitHub repo:**
   ```bash
   git init
   git add app.py requirements.txt
   git commit -m "Huliot AutoBOQ"
   git remote add origin YOUR_GITHUB_REPO
   git push -u origin main
   ```

2. **Deploy:**
   - Go to share.streamlit.io
   - Connect GitHub
   - Select repo
   - Main file: `app.py`
   - Deploy

3. **Done!** Share URL with team.

### Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`

## How to Use

### Step 1: Prepare DXF
**CRITICAL:** DWG must be exported to DXF from AutoCAD:
- File > Save As > DXF
- Select "AutoCAD 2018 DXF"

### Step 2: Upload
- Upload DXF to app
- Set SH prefix (default: "SH")
- Set detection radius (5000mm default)

### Step 3: Detect
- Click "Detect & Mark Bathrooms"
- AI clusters WC blocks spatially
- Assigns SH-01, SH-02... based on position

### Step 4: Review
- Check detected bathrooms
- See fixture counts per SH
- Preview BOQ

### Step 5: Download
- **Marked DXF** - drawing with SH labels added
- **BOQ Excel** - quantities per SH in your format

## Detection Logic

**How bathrooms are found:**

1. Scan DXF for INSERT blocks
2. Identify WC, basin, drain blocks by name pattern
3. Cluster fixtures within radius (default 5000mm)
4. Each cluster = one bathroom
5. Count fixtures per bathroom
6. Assign SH-XX label

**Block name patterns:**
- WC: `wc|toilet|closet|ewc`
- Basin: `basin|sink|wash|lav`
- Drain: `drain|fd|gully`

## BOQ Generation

**Per fixture material mapping:**

**WC fixture:**
- 110mm pipes (14.15 MTR)
- 110mm sockets (22 NOS)
- 110mm bends (15x 90°, 11x 45°)
- 110mm tees (4 NOS)
- Clamps (18 NOS)

**Basin fixture:**
- 50mm pipes (5.8 MTR)
- 50mm sockets (3 NOS)
- 50mm bends (10x 90°, 2x 45°)
- Clamps (7 NOS)

**Floor Drain:**
- MFT unit (1 NOS)
- 150mm riser (1 NOS)

**Excel format:**
- Column per SH
- Row per material
- SKU, price, discount (35%)
- Auto totals

## Troubleshooting

**No bathrooms detected:**
- Check DXF has WC block inserts
- Verify block names match patterns
- Reduce detection radius
- Open DXF in AutoCAD, check blocks exist

**Wrong fixture counts:**
- Blocks might have non-standard names
- Adjust detection radius
- Manually edit counts in Review tab

**DWG upload fails:**
- Must export to DXF from AutoCAD first
- DWG is binary, can't be parsed directly

## Customization

**Change materials database:**
Edit `materials_db` dict in `generate_boq_excel()` function.

**Change detection patterns:**
Edit `detect_bathrooms_spatial_clustering()` function patterns.

**Change SH label appearance:**
Edit `add_sh_labels_to_dxf()` text height/color.

## Technical Details

- **Backend:** Streamlit + ezdxf
- **DXF parsing:** Block INSERT entities
- **Spatial clustering:** Distance-based grouping
- **BOQ:** Pandas DataFrame → openpyxl Excel
- **Deployment:** Streamlit Community Cloud (free)

## Files Generated

1. `{project}_marked.dxf` - Original drawing + SH text labels
2. `{project}_BOQ.xlsx` - BOQ with 2 sheets:
   - Typical Floor BOQ
   - Summary

## Next Steps

**Phase 2 enhancements:**
- Vision AI for image/PDF upload
- Multi-floor support
- Custom material templates
- BOQ price auto-update
- Email automation
- Cloud storage sync

---

**Contact:** Umesh | Technical Manager (West Zone) | Huliot Pipes & Fittings
