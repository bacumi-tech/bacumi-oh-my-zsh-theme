"""Generate original MIT product icons using the public Bacumi brand subset."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def icons():
    brand = json.loads((ROOT / "brand.json").read_text())
    p = brand["master"]
    files = {}
    for mode in ("dark", "light"):
        field = p["graphite"] if mode == "dark" else p["off_white"]
        outline = p["graphite"] if mode == "light" else 'none'
        edge = p["charcoal"] if mode == "dark" else p["beige"]
        cursor = p["off_white"] if mode == "dark" else p["graphite"]
        title = f'Bacumi {brand["product"]} — {mode.title()} product icon'
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024" role="img" aria-labelledby="title description">
  <title id="title">{title}</title>
  <desc id="description">Two geometric Orange and Amber shell-prompt chevrons and a cursor, on a rounded Bacumi field.</desc>
  <rect x="32" y="32" width="960" height="960" rx="220" fill="{field}"/>
  <rect x="54" y="54" width="916" height="916" rx="198" fill="none" stroke="{edge}" stroke-width="8"/>
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M244 320L428 500L244 680M474 320L658 500L474 680" stroke="{outline}" stroke-width="96"/>
    <path d="M244 320L428 500L244 680" stroke="{p['orange']}" stroke-width="64"/>
    <path d="M474 320L658 500L474 680" stroke="{p['amber']}" stroke-width="64"/>
    <path d="M680 724H780" stroke="{cursor}" stroke-width="64"/>
  </g>
</svg>
'''
        files[f"assets/icons/icon-{mode}.svg"] = svg
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for name, content in icons().items():
        path = ROOT / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"Rebuild required: {name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    print("Bacumi product icon masters verified." if args.check else "Built Dark and Light product icons.")
