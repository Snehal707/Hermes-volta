#!/usr/bin/env python3
"""
Volta BOM Price Checker
Parses MEMORY.md for verified designs, extracts unique parts,
outputs JLCPCB/LCSC search URLs, and tracks a baseline price DB.

Usage:
    python3 tools/check_bom_prices.py

Output: JSON to stdout, updates outputs/bom_price_db.json
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

MEMORY_PATH = os.path.expanduser("~/.hermes/memories/MEMORY.md")
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "bom_price_db.json")

def parse_memory_md(path):
    """Parse MEMORY.md and return list of unique (type, value, footprint) tuples."""
    if not os.path.exists(path):
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    parts = set()
    # Find all table rows with values
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and any(u in line for u in ("kΩ", "Ω", "nF", "µF", "mF", "mH")):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 4:
                # Heuristic: look for cells with unit suffixes
                for cell in cells:
                    if re.search(r"\d+\.?\d*\s*(kΩ|Ω|nF|µF|mF|mH)", cell):
                        footprint = next((c for c in cells if "0402" in c or "0603" in c or "0805" in c or ">0402" in c), "0402")
                        # Determine type
                        val = cell.strip()
                        if "Ω" in val:
                            parts.add(("resistor", val, footprint))
                        elif "F" in val:
                            parts.add(("capacitor", val, footprint))
                        elif "H" in val:
                            parts.add(("inductor", val, footprint))

    return sorted(parts)

def load_price_db():
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "parts" not in data:
                data["parts"] = {}
            return data
    return {"parts": {}, "created": datetime.now(timezone.utc).isoformat()}

def save_price_db(db):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)

def build_search_url(part_type, value, footprint):
    """Build LCSC search URL. LCSC uses category IDs:
    Resistors: 291
    Capacitors: 293
    Inductors: 297
    """
    category_map = {
        "resistor": "291",
        "capacitor": "293",
        "inductor": "297",
    }
    cat = category_map.get(part_type, "")
    # Build aquery string
    q = f"{value} {footprint}".replace(" ", "%20")
    return f"https://lcsc.com/search?q={q}&catalog={cat}"

def build_jlcpcb_search(value, footprint):
    q = f"{value} {footprint}".replace(" ", "%20")
    return f"https://jlcpcb.com/parts/componentSearch?isSearch=true&searchTxt={q}"

def main():
    parts = parse_memory_md(MEMORY_PATH)
    db = load_price_db()
    now = datetime.now(timezone.utc).isoformat()

    out = {
        "checked_at": now,
        "parts_count": len(parts),
        "parts_to_check": [],
        "flagged_changes": [],
        "price_db_path": DB_PATH,
    }

    for ptype, value, footprint in parts:
        key = f"{ptype}:{value}:{footprint}"
        prev = db["parts"].get(key, {})
        
        entry = {
            "type": ptype,
            "value": value,
            "footprint": footprint,
            "lcsc_url": build_search_url(ptype, value, footprint),
            "jlcpcb_url": build_jlcpcb_search(value, footprint),
            "last_check": now,
            "typical_price_usd": prev.get("typical_price_usd", None),
        }

        # Flag if price known and changed >10%
        # (user manually updates typical_price_usd; automation only warns)
        if prev.get("typical_price_usd") and entry["typical_price_usd"]:
            old = float(prev["typical_price_usd"])
            new = float(entry["typical_price_usd"])
            if old > 0 and abs(new - old) / old > 0.10:
                out["flagged_changes"].append({
                    "part": key,
                    "old_price": old,
                    "new_price": new,
                    "change_pct": round((new - old) / old * 100, 2),
                })

        db["parts"][key] = entry
        out["parts_to_check"].append(entry)

    save_price_db(db)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
