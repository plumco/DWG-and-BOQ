---
name: huliot-cad-qty
description: >
  Reads Huliot CAD library DXF files and extracts fitting block quantities for BOQ preparation.
  Trigger this skill whenever the user uploads or mentions a .dxf or .dwg CAD file and wants
  to: count fittings, extract quantities, prepare a BOQ from a drawing, count pipe fittings
  from a CAD library, get a quantity takeoff, or list how many elbows/tees/reducers/connectors
  are in a drawing. Also trigger when user says "read CAD", "count fittings from drawing",
  "CAD quantity", "DXF quantity", "how many fittings", or pastes a DWG/DXF filename.
  Works for Huliot HT Pro, Ultra Silent, and PERT-AL-PERT / Heliroma product lines.
---

# Huliot CAD Quantity Extractor

Extract fitting block quantities from Huliot CAD library DXF files.
Output: structured quantity table + Excel BOQ file.

---

## Input Format

| Format | Readable? | Notes |
|--------|-----------|-------|
| `.dxf` | ✅ Yes | Native — read directly with ezdxf |
| `.dwg` | ❌ No  | Autodesk proprietary binary — must convert first |

### DWG → DXF Conversion (one-time, 30 seconds)

In AutoCAD / AutoCAD LT:
```
File → Save As → AutoCAD DXF (*.dxf) → Save
```
Or in free DWG TrueView:
```
Application Menu → Save As → AutoCAD DXF
```
Then re-upload the `.dxf` file.

---

## Workflow

### Step 1 — Check file type

```python
import os
ext = os.path.splitext(filepath)[1].lower()
if ext == '.dwg':
    # Tell user to convert and re-upload
elif ext == '.dxf':
    # Proceed
```

### Step 2 — Read DXF and extract blocks

Run `/home/claude/huliot-cad-qty/scripts/extract_qty.py` with the uploaded DXF path.

The script:
1. Opens DXF with `ezdxf`
2. Counts all `INSERT` entities (block insertions) in modelspace
3. Parses block names to identify Huliot product series + size
4. Counts `LINE` / `LWPOLYLINE` entities per layer for pipe length estimation
5. Outputs:
   - Console summary table
   - `quantity_takeoff.xlsx` with formatted BOQ
   - `blocks_raw.csv` with raw counts

### Step 3 — Parse block names

Huliot block name convention (typical):
```
HULIOT_[TYPE]_[ANGLE]_[SIZE]
US_[TYPE]_[SIZE]         ← Ultra Silent
PAP_[TYPE]_[SIZE]        ← PERT-AL-PERT / Heliroma
```

Size codes: `50`, `75`, `90`, `110`, `125`, `160` (DN in mm)

| Block name pattern | Category | Product line |
|---|---|---|
| `HULIOT_*` or `HTP_*` | Fitting | HT Pro |
| `US_*` or `ULTRA_*` | Fitting | Ultra Silent |
| `PAP_*` or `HELIROMA_*` | Fitting | PERT-AL-PERT |
| Layer `PIPE_*` or `DRAIN_*` | Pipe run | (measure length) |
| `*ELBOW*` | Elbow | — |
| `*TEE*` or `*WYE*` | Tee / Wye | — |
| `*REDUCER*` or `*REDUC*` | Reducer | — |
| `*TRAP*` | Trap | — |
| `*CONNECTOR*` or `*WC*` | WC connector | — |
| `*CAP*` or `*PLUG*` | End cap | — |
| `*ACCESS*` or `*CLEAN*` | Access door | — |
| `*CLAMP*` | Clamp / bracket | — |

### Step 4 — Output BOQ

Excel sheet columns:
```
Sr | Block Name | Product Line | Type | Size (DN) | Qty | Unit | Remarks
```

Group by: Product Line → Size → Type

### Step 5 — Pipe length (optional)

If `LINE` or `LWPOLYLINE` entities exist on pipe layers:
- Sum lengths per layer
- Convert EMU/drawing units → meters (ask user for drawing scale if unknown)
- Add as separate "Pipes" section in BOQ

---

## Script Location

`/home/claude/huliot-cad-qty/scripts/extract_qty.py`

Read and run this script. Pass the uploaded DXF file path as argument.

---

## Dependencies

```bash
pip install ezdxf openpyxl --break-system-packages -q
```

---

## Error Handling

| Error | Action |
|---|---|
| `File is not a DXF file` | User uploaded DWG — request DXF export |
| `No INSERT entities found` | Drawing has no block references — check if symbols are exploded |
| `Unknown block names` | Show raw names, ask user to identify series |
| `Scale unclear` | Show line counts, ask user for drawing scale for length calc |

---

## Output Example

```
=== HULIOT QUANTITY TAKEOFF ===
Drawing: Kamkar_Park_B1_Drainage.dxf

HT PRO FITTINGS
  Elbow 90° DN110          x 12
  Elbow 90° DN75           x  8
  Tee DN110                x  6
  Reducer 110×75           x  4

ULTRA SILENT FITTINGS
  Elbow 87.5° DN110        x  5
  WC Connector DN110       x  7
  Access Door DN110        x  3

SUMMARY: 45 fittings total
Excel BOQ saved: quantity_takeoff_Kamkar_Park.xlsx
```
