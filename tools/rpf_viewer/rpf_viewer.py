"""Visor local de archivos RPF9 (magic 9FPR) de este dump.

Muestra el inventario y el encabezado en claro de 64 bytes. El indice de
cada archivo empieza en el offset 0x40 y no es legible: no hay listado ni
extraccion de entradas.

Uso:
  python rpf_viewer.py
  python rpf_viewer.py --list
  python rpf_viewer.py --info levels.rpf
  python rpf_viewer.py --check
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import threading
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

MAGIC = b"9FPR"
HEADER_SIZE = 0x40
HEX_BYTES = 0x100
TOC_SAMPLE = 0x10000
SKIP_DIRS = {"docs", "XboxCompat", "tools", ".git"}

# Observed on every archive in this dump. Used only to flag a header as
# consistent with the documented layout, not as a key or a decoder.
CONST_18 = 0x00047A00
CONST_1C = 0x00000150
CONST_30 = 0x10


def default_root() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[2]
    if (candidate / "appdata0.rpf").is_file():
        return candidate
    cwd = Path.cwd()
    if (cwd / "appdata0.rpf").is_file():
        return cwd
    return candidate


def shannon_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in Counter(data).values())


def read_at(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as handle:
        handle.seek(offset)
        return handle.read(size)


def parse_header(blob: bytes) -> dict:
    if len(blob) < HEADER_SIZE:
        return {
            "valid": False,
            "reason": "archivo mas corto que el encabezado de 64 bytes",
        }
    magic = blob[0:4]
    field_a = int.from_bytes(blob[4:8], "little")
    field_b = int.from_bytes(blob[8:12], "little")
    field_c = int.from_bytes(blob[12:16], "little")
    ident = blob[0x10:0x18]
    const_18 = int.from_bytes(blob[0x18:0x1C], "little")
    const_1c = int.from_bytes(blob[0x1C:0x20], "little")
    enum_20 = int.from_bytes(blob[0x20:0x22], "little")
    field_22 = int.from_bytes(blob[0x22:0x24], "little")
    count_24 = int.from_bytes(blob[0x24:0x28], "little")
    selector = int.from_bytes(blob[0x28:0x2C], "little")
    flags = blob[0x2C:0x30]
    const_30 = int.from_bytes(blob[0x30:0x34], "little")
    padding = blob[0x34:0x40]
    checks = {
        "magic": magic == MAGIC,
        "const_18": const_18 == CONST_18,
        "const_1c": const_1c == CONST_1C,
        "const_30": const_30 == CONST_30,
        "field_22": field_22 == 1,
        "version_byte": flags[2] == 0x09,
        "flag1": flags[1] == 0x0F,
        "padding": padding == b"\x00" * 12,
        "a_gt_b": field_a > field_b,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "magic": magic.decode("ascii", "replace"),
        "field_a": field_a,
        "field_b": field_b,
        "field_c": field_c,
        "ident_hex": ident.hex(),
        "const_18": const_18,
        "const_1c": const_1c,
        "enum_20": enum_20,
        "field_22": field_22,
        "count": count_24,
        "selector": selector,
        "selector_hex": f"{selector:08x}",
        "flags_hex": flags.hex(),
        "flag0": flags[0],
        "flag1": flags[1],
        "version_byte": flags[2],
        "const_30": const_30,
        "padding_zero": padding == b"\x00" * 12,
    }


def inspect_rpf(path: Path, root: Path) -> dict:
    size = path.stat().st_size
    blob = read_at(path, 0, HEX_BYTES)
    header = parse_header(blob)
    sample_len = 0
    entropy = None
    toc_prefix = ""
    if header.get("magic") == "9FPR" and size > HEADER_SIZE:
        field_b = int(header.get("field_b") or 0)
        sample_len = min(field_b or TOC_SAMPLE, TOC_SAMPLE, size - HEADER_SIZE)
        sample = read_at(path, HEADER_SIZE, max(sample_len, 32))
        if sample_len:
            entropy = round(shannon_entropy(sample[:sample_len]), 3)
        toc_prefix = sample[:32].hex()
    rel = path.relative_to(root).as_posix()
    parent = path.parent.relative_to(root).as_posix()
    if parent == ".":
        parent = ""
    return {
        "rel": rel,
        "name": path.name,
        "dir": parent,
        "size": size,
        "header": header,
        "toc_entropy": entropy,
        "toc_sample_bytes": sample_len,
        "toc_prefix": toc_prefix,
        "hex": blob.hex(),
        "toc_status": "protected" if (entropy or 0) >= 7.0 else "unknown",
    }


def scan(root: Path) -> dict:
    archives = []
    other = Counter()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        for name in filenames:
            path = Path(dirpath) / name
            if name.lower().endswith(".rpf"):
                archives.append(inspect_rpf(path, root))
            else:
                other[path.suffix.lower() or "(sin extension)"] += 1
    archives.sort(key=lambda item: item["rel"].lower())
    prefixes = {item["toc_prefix"] for item in archives if item["toc_prefix"]}
    shared = next(iter(prefixes)) if len(prefixes) == 1 else ""
    return {
        "root": str(root),
        "title": "Grand Theft Auto VI",
        "version": "1.0.2.1",
        "platform": "Xbox Series",
        "archive_count": len(archives),
        "total_bytes": sum(item["size"] for item in archives),
        "other_counts": dict(sorted(other.items())),
        "shared_toc_prefix": shared,
        "archives": archives,
        "limitation": (
            "El indice de cada RPF9 esta protegido desde el byte 0x40. "
            "Este visor no lista ni extrae entradas."
        ),
    }


def fmt_size(n: int) -> str:
    value = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{n} B"


def cmd_list(report: dict) -> int:
    print(f"{report['archive_count']} archivos RPF9  {fmt_size(report['total_bytes'])}")
    print(f"{'archivo':<62} {'tamano':>12} {'conteo':>7} {'entropia':>8} selector")
    for item in report["archives"]:
        header = item["header"]
        entropy = item["toc_entropy"]
        entropy_text = f"{entropy:.2f}" if isinstance(entropy, float) else "-"
        print(
            f"{item['rel']:<62} {fmt_size(item['size']):>12} "
            f"{header.get('count', 0):7d} {entropy_text:>8} {header.get('selector_hex', '')}"
        )
    print(report["limitation"])
    return 0


def cmd_info(report: dict, rel: str) -> int:
    want = rel.replace("\\", "/").lstrip("/")
    match = next((item for item in report["archives"] if item["rel"].lower() == want.lower()), None)
    if match is None:
        print(f"no esta en el inventario: {rel}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in match.items() if k != "hex"}, indent=2))
    return 0


def cmd_check(report: dict) -> int:
    failures = []
    if report["archive_count"] != 22:
        failures.append(f"se esperaban 22 rpf, hay {report['archive_count']}")
    if not report["shared_toc_prefix"] or len(report["shared_toc_prefix"]) != 64:
        failures.append("el prefijo de 32 bytes en 0x40 no es comun a todos")
    for item in report["archives"]:
        header = item["header"]
        if not header.get("valid"):
            failures.append(f"{item['rel']}: encabezado fuera del patron documentado ({header.get('checks')})")
        if item["size"] <= header.get("field_a", 0):
            failures.append(f"{item['rel']}: campo A no cabe en el archivo")
        entropy = item["toc_entropy"]
        if not isinstance(entropy, float) or entropy < 7.4:
            failures.append(f"{item['rel']}: entropia del indice {entropy}, se esperaba >= 7.4")
    if failures:
        print("CHECK FAIL")
        for line in failures:
            print(" -", line)
        return 1
    print(f"CHECK OK  {report['archive_count']} RPF9, encabezado en claro, indice protegido")
    return 0


PAGE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RPF Viewer</title>
<style>
  :root {
    --bg: #101114;
    --panel: #181b21;
    --panel-2: #20242c;
    --line: #2d3340;
    --text: #e7e9ee;
    --muted: #8e97a8;
    --gold: #e4b15a;
    --gold-dim: rgba(228, 177, 90, 0.14);
    --red: #e36b6b;
    --red-dim: rgba(227, 107, 107, 0.12);
    --ok: #7dcea0;
    --plain: #d7deea;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font: 14px/1.45 "Segoe UI", sans-serif;
    display: grid;
    grid-template-rows: 56px 1fr 36px;
    height: 100vh;
  }
  header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 16px;
    border-bottom: 1px solid var(--line);
    background: #14161b;
  }
  header h1 { font-size: 16px; font-weight: 650; margin: 0; letter-spacing: 0.02em; }
  header h1 span { color: var(--gold); }
  .meta { color: var(--muted); font-size: 12px; }
  .spacer { flex: 1; }
  button, input {
    font: inherit;
    color: var(--text);
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: 6px;
  }
  button { padding: 6px 10px; cursor: pointer; }
  button:hover { border-color: var(--gold); }
  main { display: grid; grid-template-columns: 320px 1fr; min-height: 0; }
  aside, section { min-height: 0; }
  aside {
    border-right: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    background: #14171c;
  }
  .search { padding: 10px; border-bottom: 1px solid var(--line); }
  .search input { width: 100%; padding: 8px 10px; outline: none; }
  .search input:focus { border-color: var(--gold); }
  .tree { overflow: auto; padding: 8px 0 16px; }
  .group {
    padding: 10px 14px 4px;
    color: var(--muted);
    font-size: 11px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .row {
    display: grid;
    grid-template-columns: 16px 1fr auto;
    gap: 8px;
    align-items: center;
    padding: 6px 14px;
    cursor: pointer;
    border-left: 2px solid transparent;
  }
  .row:hover { background: var(--panel-2); }
  .row.active { background: var(--gold-dim); border-left-color: var(--gold); }
  .row .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .row .size { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
  .lock { color: var(--red); font-size: 12px; }
  section { overflow: auto; padding: 20px 24px 32px; }
  .empty { color: var(--muted); max-width: 720px; }
  h2 { margin: 0 0 4px; font-size: 22px; font-weight: 640; }
  .sub { color: var(--muted); margin-bottom: 16px; }
  .banner {
    background: var(--red-dim);
    border: 1px solid rgba(227, 107, 107, 0.4);
    color: #f0c8c8;
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 16px;
  }
  .cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; }
  .card .k { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
  .card .v { font-size: 18px; margin-top: 4px; font-variant-numeric: tabular-nums; }
  .tabs { display: flex; gap: 6px; margin-bottom: 12px; }
  .tabs button.active { border-color: var(--gold); color: var(--gold); }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 7px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  tr.click:hover { background: var(--panel); cursor: pointer; }
  tr.picked { background: var(--gold-dim); }
  code, .mono { font-family: Consolas, "Cascadia Mono", monospace; font-size: 12.5px; }
  .hex { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 12px; overflow: auto; }
  .hex .off { color: var(--muted); }
  .hex .plain { color: var(--plain); }
  .hex .cipher { color: #f0a0a0; }
  .tag { display: inline-block; padding: 1px 6px; border-radius: 999px; font-size: 11px; }
  .tag.low { background: #2a261c; color: var(--gold); }
  .tag.high { background: #1a2a22; color: var(--ok); }
  footer {
    border-top: 1px solid var(--line);
    color: var(--muted);
    display: flex;
    align-items: center;
    padding: 0 16px;
    font-size: 12px;
    gap: 12px;
  }
  .peers { color: var(--muted); }
  @media (max-width: 980px) {
    main { grid-template-columns: 1fr; }
    aside { max-height: 40vh; }
    .cards { grid-template-columns: 1fr 1fr; }
  }
</style>
</head>
<body>
<header>
  <h1><span>RPF</span> Viewer</h1>
  <div class="meta" id="pkg"></div>
  <div class="spacer"></div>
  <div class="meta" id="totals"></div>
  <button id="reload" type="button">Recargar</button>
</header>
<main>
  <aside>
    <div class="search"><input id="q" type="search" placeholder="Buscar archivo..." autocomplete="off"></div>
    <div class="tree" id="tree"></div>
  </aside>
  <section id="view"></section>
</main>
<footer>
  <span id="foot"></span>
</footer>
<script>
const state = { report: null, selected: null, tab: "resumen", query: "" };

function size(n) {
  const u = ["B", "KiB", "MiB", "GiB", "TiB"];
  let v = n, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v.toString() : v.toFixed(2)) + " " + u[i];
}
function hex(n, w = 8) { return "0x" + (n >>> 0).toString(16).padStart(w, "0"); }
function el(tag, attrs, kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const kid of kids || []) node.append(kid);
  return node;
}
function text(s) { return document.createTextNode(s); }

function groupsOf(archives) {
  const map = new Map();
  for (const item of archives) {
    const key = item.dir || "(raiz)";
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return [...map.entries()];
}

function filtered() {
  const q = state.query.trim().toLowerCase();
  const all = state.report.archives;
  if (!q) return all;
  return all.filter(a => a.rel.toLowerCase().includes(q) || (a.header.selector_hex || "").includes(q));
}

function select(rel) {
  state.selected = rel || null;
  if (rel) location.hash = encodeURIComponent(rel);
  else history.replaceState(null, "", location.pathname);
  renderTree();
  if (rel) renderDetail();
  else renderDashboard();
}

function renderTree() {
  const tree = document.getElementById("tree");
  tree.replaceChildren();
  const all = el("div", {
    class: "row" + (state.selected ? "" : " active"),
    onclick: () => select(null)
  }, [
    el("span", { class: "lock" }, [text("")]),
    el("span", { class: "name" }, [text("Todos los archivos")]),
    el("span", { class: "size" }, [text(String(state.report.archive_count))])
  ]);
  tree.append(all);
  const items = filtered();
  if (!items.length) {
    tree.append(el("div", { class: "group" }, [text("sin resultados")]));
    return;
  }
  for (const [dir, rows] of groupsOf(items)) {
    tree.append(el("div", { class: "group" }, [text(dir)]));
    for (const item of rows) {
      const active = state.selected === item.rel;
      const row = el("div", {
        class: "row" + (active ? " active" : ""),
        onclick: () => select(item.rel)
      }, [
        el("span", { class: "lock", title: "indice protegido" }, [text("\u25A0")]),
        el("span", { class: "name" }, [text(item.name)]),
        el("span", { class: "size" }, [text(size(item.size))])
      ]);
      tree.append(row);
    }
  }
}

function peers(item, key) {
  return state.report.archives
    .filter(other => other !== item && other.header[key] === item.header[key])
    .map(other => other.rel);
}

function fieldRows(item) {
  const h = item.header;
  const selectorPeers = peers(item, "selector");
  const enumPeers = peers(item, "enum_20");
  return [
    ["0x00", "u32", h.magic + "  (" + hex(0x52504639) + ")", "Magic RPF9. En disco los bytes son 39 46 50 52.", "alta"],
    ["0x04", "u32", h.field_a.toLocaleString("es") + "  (" + hex(h.field_a) + ")", "Tamano. Siempre mayor que el campo de 0x08. Significado exacto no confirmado.", "baja"],
    ["0x08", "u32", h.field_b.toLocaleString("es") + "  (" + hex(h.field_b) + ")", "Tamano, menor que 0x04. La muestra de entropia usa esta longitud.", "baja"],
    ["0x0C", "u32", h.field_c.toLocaleString("es") + "  (" + hex(h.field_c) + ")", "Tercer tamano o contador. No es el numero de entradas.", "baja"],
    ["0x10", "8 B", h.ident_hex, "Identificador opaco, distinto en cada archivo.", "baja"],
    ["0x18", "u32", hex(h.const_18), "Misma constante en todos los RPF leidos.", "alta"],
    ["0x1C", "u32", hex(h.const_1c), "Misma constante en todos los RPF leidos.", "alta"],
    ["0x20", "u16", String(h.enum_20), "Valor pequeno (3 a 7). Lo comparten: " + (enumPeers.length ? enumPeers.join(", ") : "nadie mas") + ".", "baja"],
    ["0x22", "u16", String(h.field_22), "Siempre 1 en este dump.", "alta"],
    ["0x24", "u32", h.count.toLocaleString("es"), "Crece con el archivo (appdata0 = 2, levels = 2078). Posible conteo de entradas; las entradas no estan en claro.", "baja"],
    ["0x28", "u32", h.selector_hex, "Uno de cuatro selectores. Lo comparten: " + (selectorPeers.length ? selectorPeers.join(", ") : "nadie mas") + ".", "baja"],
    ["0x2C", "4 B", h.flags_hex, "Byte 0 = " + h.flag0 + ", byte 1 = 0x0f, byte 2 = " + h.version_byte + " (version 9), byte 3 = 0.", "baja"],
    ["0x30", "u32", hex(h.const_30, 2), "Constante 0x10 en todos los RPF leidos.", "alta"],
    ["0x34", "12 B", h.padding_zero ? "00 \u00d7 12" : "no es cero", "Relleno.", "alta"],
    ["0x40", "indice", (item.toc_entropy ?? "-") + " bits/byte", "Muestra de " + item.toc_sample_bytes.toLocaleString("es") + " bytes. Entropia alta: el indice no se puede listar.", "alta"]
  ];
}

function renderHex(item) {
  const raw = item.hex;
  const wrap = el("div", { class: "hex mono" });
  for (let off = 0; off < raw.length / 2; off += 16) {
    const line = el("div");
    line.append(el("span", { class: "off" }, [text(off.toString(16).padStart(4, "0") + "  ")]));
    let ascii = "";
    for (let i = 0; i < 16; i++) {
      const pos = off + i;
      if (pos >= raw.length / 2) break;
      const byte = parseInt(raw.substr(pos * 2, 2), 16);
      const cls = pos < 0x40 ? "plain" : "cipher";
      line.append(el("span", { class: cls }, [text(byte.toString(16).padStart(2, "0") + " ")]));
      ascii += (byte >= 32 && byte < 127) ? String.fromCharCode(byte) : ".";
    }
    line.append(el("span", { class: "off" }, [text(" " + ascii)]));
    wrap.append(line);
  }
  const note = el("p", { class: "sub" }, [
    text("Dorado: encabezado en claro (0x00\u20130x3F). Rojo: inicio del indice protegido. Prefijo comun de 32 bytes en 0x40: ")
  ]);
  note.append(el("span", { class: "mono" }, [text(state.report.shared_toc_prefix || "(no comun)")]));
  return [note, wrap];
}

function renderSummary(item) {
  const h = item.header;
  const cards = [
    ["Tamano", size(item.size)],
    ["Campo 0x24", h.count.toLocaleString("es")],
    ["Entropia del indice", (item.toc_entropy ?? "-") + " bit/B"],
    ["Selector", h.selector_hex]
  ].map(([k, v]) => el("div", { class: "card" }, [
    el("div", { class: "k" }, [text(k)]),
    el("div", { class: "v" }, [text(v)])
  ]));
  const banner = el("div", { class: "banner" }, [
    text("No hay lista de archivos internos. OpenIV puede abrir un RPF de GTA V porque ese indice se descifra con el lector conocido. Aqui el indice sale cifrado o comprimido desde el byte 0x40, y el ejecutable que lo lee (game_scarlett_master.exe) no esta en el dump.")
  ]);
  const box = el("div");
  box.append(el("div", { class: "cards" }, cards), banner);
  const rows = fieldRows(item).filter(r => ["0x00", "0x24", "0x28", "0x2C", "0x40"].includes(r[0]));
  box.append(renderTable(rows));
  return box;
}

function renderTable(rows) {
  const table = el("table");
  const head = el("tr");
  for (const label of ["Offset", "Tipo", "Valor", "Lectura", "Confianza"]) {
    head.append(el("th", null, [text(label)]));
  }
  table.append(el("thead", null, [head]));
  const body = el("tbody");
  for (const [off, type, value, meaning, trust] of rows) {
    body.append(el("tr", null, [
      el("td", { class: "mono" }, [text(off)]),
      el("td", { class: "mono" }, [text(type)]),
      el("td", { class: "mono" }, [text(value)]),
      el("td", null, [text(meaning)]),
      el("td", null, [el("span", { class: "tag " + (trust === "alta" ? "high" : "low") }, [text(trust)])])
    ]));
  }
  table.append(body);
  return table;
}

function renderDashboard() {
  const view = document.getElementById("view");
  const report = state.report;
  view.replaceChildren();
  view.append(el("h2", null, [text("Archivos del paquete")]));
  view.append(el("p", { class: "sub" }, [
    text(report.archive_count + " archivos RPF9, " + size(report.total_bytes) + ". Elegi uno para ver el encabezado. El cuadrado rojo marca un indice que este visor no abre.")
  ]));
  const others = Object.entries(report.other_counts);
  if (others.length) {
    view.append(el("p", { class: "sub" }, [
      text("Fuera de los RPF, el dump tambien tiene " + others.map(([ext, n]) => n + " " + ext).join(", ") + ". Esos formatos no se abren aca.")
    ]));
  }
  const table = el("table");
  const head = el("tr");
  for (const [label, cls] of [["Archivo", ""], ["Tamano", "num"], ["0x24", "num"], ["Enum", "num"], ["Selector", ""], ["Flags", ""], ["Entropia", "num"]]) {
    head.append(el("th", { class: cls }, [text(label)]));
  }
  table.append(el("thead", null, [head]));
  const body = el("tbody");
  for (const item of filtered()) {
    const h = item.header;
    body.append(el("tr", { class: "click" + (state.selected === item.rel ? " picked" : ""), onclick: () => select(item.rel) }, [
      el("td", null, [text(item.rel)]),
      el("td", { class: "num" }, [text(size(item.size))]),
      el("td", { class: "num" }, [text(String(h.count))]),
      el("td", { class: "num" }, [text(String(h.enum_20))]),
      el("td", { class: "mono" }, [text(h.selector_hex)]),
      el("td", { class: "mono" }, [text(h.flags_hex)]),
      el("td", { class: "num" }, [text(item.toc_entropy == null ? "-" : item.toc_entropy.toFixed(2))])
    ]));
  }
  table.append(body);
  view.append(table);
}

function renderDetail() {
  const item = state.report.archives.find(a => a.rel === state.selected);
  const view = document.getElementById("view");
  view.replaceChildren();
  if (!item) { renderDashboard(); return; }
  view.append(el("h2", null, [text(item.rel)]));
  view.append(el("p", { class: "sub" }, [
    text(size(item.size) + "  \u00b7  " + item.size.toLocaleString("es") + " bytes  \u00b7  encabezado " + (item.header.valid ? "consistente con RPF9" : "distinto del patron de este dump"))
  ]));
  const tabs = el("div", { class: "tabs" });
  for (const [id, label] of [["resumen", "Resumen"], ["encabezado", "Encabezado"], ["hex", "Hex"]]) {
    tabs.append(el("button", { class: state.tab === id ? "active" : "", type: "button", onclick: () => { state.tab = id; renderDetail(); } }, [text(label)]));
  }
  view.append(tabs);
  if (state.tab === "resumen") view.append(renderSummary(item));
  else if (state.tab === "encabezado") view.append(renderTable(fieldRows(item)));
  else view.append(...renderHex(item));
}


function renderAll() {
  const report = state.report;
  document.getElementById("pkg").textContent = report.title + "  \u00b7  " + report.platform + "  \u00b7  " + report.version;
  document.getElementById("totals").textContent = report.archive_count + " RPF  \u00b7  " + size(report.total_bytes);
  document.getElementById("foot").textContent = report.limitation;
  renderTree();
  if (state.selected) renderDetail();
  else renderDashboard();
}

async function load() {
  const response = await fetch("/api/scan");
  if (!response.ok) throw new Error("scan " + response.status);
  state.report = await response.json();
  const fromHash = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (fromHash && state.report.archives.some(a => a.rel === fromHash)) state.selected = fromHash;
  renderAll();
}

document.getElementById("q").addEventListener("input", (event) => {
  state.query = event.target.value;
  renderTree();
  if (!state.selected) renderDashboard();
});
document.getElementById("reload").addEventListener("click", () => load().catch(showError));
window.addEventListener("hashchange", () => {
  const rel = decodeURIComponent(location.hash.replace(/^#/, ""));
  if (!state.report) return;
  if (!rel) { if (state.selected) select(null); return; }
  if (state.report.archives.some(a => a.rel === rel) && rel !== state.selected) select(rel);
});

function showError(err) {
  document.getElementById("view").replaceChildren(
    el("h2", null, [text("No se pudo leer el dump")]),
    el("p", { class: "empty" }, [text(String(err && err.message || err))])
  );
}

load().catch(showError);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    report = None
    root: Path

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/scan":
            refresh = parse_qs(parsed.query).get("refresh", ["0"])[0] == "1"
            if refresh or Handler.report is None:
                Handler.report = scan(Handler.root)
            body = json.dumps(Handler.report).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def serve(root: Path, port: int, open_browser: bool) -> int:
    Handler.root = root
    Handler.report = scan(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"RPF Viewer  {Handler.report['archive_count']} archivos  {url}")
    print(Handler.report["limitation"])
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ndetenido")
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Visor de encabezados RPF9 de este dump")
    parser.add_argument("--root", type=Path, default=None, help="carpeta del dump (por defecto, la raiz del proyecto)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--list", action="store_true", help="imprimir el inventario y salir")
    parser.add_argument("--info", metavar="REL", help="imprimir el encabezado de un .rpf y salir")
    parser.add_argument("--check", action="store_true", help="comprobar los 22 encabezados contra el patron documentado")
    args = parser.parse_args(argv)
    root = (args.root or default_root()).resolve()
    if not root.is_dir():
        print(f"no existe la carpeta: {root}", file=sys.stderr)
        return 1
    if args.list or args.info or args.check:
        report = scan(root)
        code = 0
        if args.check:
            code = cmd_check(report)
        if code == 0 and args.list:
            code = cmd_list(report)
        if code == 0 and args.info:
            code = cmd_info(report, args.info)
        return code
    return serve(root, args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    raise SystemExit(main())
