from __future__ import annotations

import csv
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import TypedDict
import xml.etree.ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAW_NS = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

NS = {
    "main": MAIN_NS,
    "r": REL_NS,
    "pr": PKG_REL_NS,
    "xdr": DRAW_NS,
    "a": A_NS,
}


class DrawingRecord(TypedDict):
    anchor_no: int
    excel_row: int
    excel_column: int | None
    embed_id: str
    media_path: str


def norm_zip_path(base_file: str, target: str) -> str:
    """Bir OOXML ilişki hedefini ZIP içindeki gerçek yola dönüştürür."""
    base_dir = PurePosixPath(base_file).parent
    combined = base_dir / target
    parts: list[str] = []

    for part in combined.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
        else:
            parts.append(part)

    return "/".join(parts)


def rels_path_for(xml_path: str) -> str:
    path = PurePosixPath(xml_path)
    return str(path.parent / "_rels" / f"{path.name}.rels")


def read_xml(zf: zipfile.ZipFile, path: str) -> ET.Element:
    with zf.open(path) as file:
        return ET.parse(file).getroot()


def load_relationships(
    zf: zipfile.ZipFile,
    source_xml: str,
) -> dict[str, dict[str, str]]:
    rels_path = rels_path_for(source_xml)
    if rels_path not in zf.namelist():
        return {}

    root = read_xml(zf, rels_path)
    relationships: dict[str, dict[str, str]] = {}

    for rel in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
        relationship_id = rel.attrib.get("Id", "")
        relationships[relationship_id] = {
            "target": rel.attrib.get("Target", ""),
            "type": rel.attrib.get("Type", ""),
            "mode": rel.attrib.get("TargetMode", ""),
        }

    return relationships


def load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in zf.namelist():
        return []

    root = read_xml(zf, path)
    values: list[str] = []

    for string_item in root.findall("main:si", NS):
        texts = [node.text or "" for node in string_item.findall(".//main:t", NS)]
        values.append("".join(texts))

    return values


def column_letters_to_number(letters: str) -> int:
    result = 0
    for char in letters:
        if char.isalpha():
            result = result * 26 + ord(char.upper()) - 64
    return result


def split_cell_ref(reference: str) -> tuple[int, int]:
    letters = "".join(char for char in reference if char.isalpha())
    digits = "".join(char for char in reference if char.isdigit())
    return column_letters_to_number(letters), int(digits or 0)


def get_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")

    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", NS))

    value_node = cell.find("main:v", NS)
    raw_value = "" if value_node is None or value_node.text is None else value_node.text

    if cell_type == "s":
        try:
            return shared_strings[int(raw_value)]
        except (ValueError, IndexError):
            return raw_value

    if cell_type == "b":
        return "TRUE" if raw_value == "1" else "FALSE"

    return raw_value


def load_sheet_rows(
    zf: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> tuple[dict[int, dict[int, str]], ET.Element]:
    root = read_xml(zf, sheet_path)
    rows: dict[int, dict[int, str]] = {}

    for cell in root.findall(".//main:sheetData/main:row/main:c", NS):
        cell_reference = cell.attrib.get("r", "")
        column_number, row_number = split_cell_ref(cell_reference)

        if row_number == 0 or column_number == 0:
            continue

        rows.setdefault(row_number, {})[column_number] = get_cell_value(
            cell, shared_strings
        )

    return rows, root


def find_sheet(
    zf: zipfile.ZipFile,
    requested_name: str | None,
) -> tuple[str, str, str]:
    """İstenen veya ilk görünür worksheet'i ve XML yolunu bulur."""
    workbook_path = "xl/workbook.xml"
    workbook_root = read_xml(zf, workbook_path)
    workbook_rels = load_relationships(zf, workbook_path)

    sheets: list[tuple[str, str, str]] = []

    for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
        name = sheet.attrib.get("name", "")
        state = sheet.attrib.get("state", "visible")
        relationship_id = sheet.attrib.get(f"{{{REL_NS}}}id", "")
        relationship = workbook_rels.get(relationship_id, {})
        target = relationship.get("target", "")
        sheet_path = norm_zip_path(workbook_path, target) if target else ""
        sheets.append((name, state, sheet_path))

    if requested_name:
        for name, state, sheet_path in sheets:
            if name.casefold() == requested_name.casefold():
                return name, state, sheet_path
        available = ", ".join(name for name, _, _ in sheets)
        raise ValueError(
            f"'{requested_name}' adlı sayfa bulunamadı. Mevcut sayfalar: {available}"
        )

    for name, state, sheet_path in sheets:
        if state == "visible":
            return name, state, sheet_path

    if sheets:
        return sheets[0]

    raise ValueError("Workbook içinde worksheet bulunamadı.")


def find_sheet_drawing(
    zf: zipfile.ZipFile,
    sheet_path: str,
    sheet_root: ET.Element,
) -> str:
    drawing_node = sheet_root.find("main:drawing", NS)
    if drawing_node is None:
        raise ValueError("Seçilen worksheet içinde drawing ilişkisi bulunamadı.")

    relationship_id = drawing_node.attrib.get(f"{{{REL_NS}}}id", "")
    if not relationship_id:
        raise ValueError("Worksheet drawing ilişki kimliği boş.")

    relationships = load_relationships(zf, sheet_path)
    relationship = relationships.get(relationship_id)
    if not relationship:
        raise ValueError("Worksheet drawing ilişkisi çözümlenemedi.")

    drawing_path = norm_zip_path(sheet_path, relationship["target"])
    if drawing_path not in zf.namelist():
        raise ValueError(f"Drawing XML bulunamadı: {drawing_path}")

    return drawing_path


def parse_drawing(
    zf: zipfile.ZipFile,
    drawing_path: str,
) -> list[DrawingRecord]:
    root = read_xml(zf, drawing_path)
    relationships = load_relationships(zf, drawing_path)

    anchors = (
        root.findall("xdr:twoCellAnchor", NS)
        + root.findall("xdr:oneCellAnchor", NS)
        + root.findall("xdr:absoluteAnchor", NS)
    )

    records: list[DrawingRecord] = []

    for anchor_number, anchor in enumerate(anchors, start=1):
        from_node = anchor.find("xdr:from", NS)
        if from_node is None:
            continue

        row_node = from_node.find("xdr:row", NS)
        column_node = from_node.find("xdr:col", NS)
        if row_node is None or row_node.text is None:
            continue

        # OOXML sıfır tabanlıdır; Excel satırı bir tabanlıdır.
        excel_row = int(row_node.text) + 1
        excel_column = (
            int(column_node.text) + 1
            if column_node is not None and column_node.text is not None
            else None
        )

        blip = anchor.find(".//a:blip", NS)
        if blip is None:
            continue

        embed_id = blip.attrib.get(f"{{{REL_NS}}}embed", "")
        relationship = relationships.get(embed_id)
        if not relationship:
            continue

        media_path = norm_zip_path(drawing_path, relationship["target"])
        records.append(
            {
                "anchor_no": anchor_number,
                "excel_row": excel_row,
                "excel_column": excel_column,
                "embed_id": embed_id,
                "media_path": media_path,
            }
        )

    return records


def clean_stock_code(value: object) -> str:
    text = str(value).strip()
    if not text:
        return ""

    # macOS/Windows için sakıncalı dosya adı karakterleri.
    text = re.sub(r'[<>:"/\\|?*;]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("._ ")

    # Çok uzun dosya adlarını sınırlayarak dosya sistemi sorunlarını önler.
    return text[:180]


def unique_output_path(
    output_dir: Path,
    clean_code: str,
    extension: str,
    counters: dict[str, int],
) -> Path:
    counters[clean_code] += 1
    sequence = counters[clean_code]
    return output_dir / f"{clean_code}_{sequence}{extension.lower()}"


def main() -> int:
    if len(sys.argv) < 2:
        print(
            "Kullanım: python3 gorsel_esle_duzeltilmis.py urun_listesi.xlsx [sheet_adi]"
        )
        print(
            "Örnek:    python3 gorsel_esle_duzeltilmis.py urun_listesi.xlsx Metaks"
        )
        return 1

    excel_path = Path(sys.argv[1]).expanduser().resolve()
    requested_sheet = sys.argv[2] if len(sys.argv) >= 3 else None

    if not excel_path.exists():
        print(f"❌ Excel dosyası bulunamadı: {excel_path}")
        return 1

    output_dir = excel_path.parent / "urun_gorselleri_stoklu_duzeltilmis"
    output_dir.mkdir(exist_ok=True)

    mapping_csv = output_dir / "gorsel_esleme_raporu.csv"
    counters: dict[str, int] = defaultdict(int)
    report_rows: list[dict[str, object]] = []

    copied_count = 0
    missing_stock_count = 0
    missing_media_count = 0

    print("🔍 Excel workbook, worksheet ve drawing ilişkileri okunuyor...")

    try:
        with zipfile.ZipFile(excel_path) as zf:
            names = set(zf.namelist())
            shared_strings = load_shared_strings(zf)

            sheet_name, sheet_state, sheet_path = find_sheet(zf, requested_sheet)
            if not sheet_path or sheet_path not in names:
                raise ValueError(f"Worksheet XML bulunamadı: {sheet_path}")

            rows, sheet_root = load_sheet_rows(zf, sheet_path, shared_strings)
            drawing_path = find_sheet_drawing(zf, sheet_path, sheet_root)
            records = parse_drawing(zf, drawing_path)

            print(f"📄 Seçilen sheet: {sheet_name} ({sheet_state})")
            print(f"🗺️ Bağlı drawing: {drawing_path}")
            print(f"🖼️ Bulunan resim konumu: {len(records)}")

            for record in records:
                excel_row = record["excel_row"]
                media_path = record["media_path"]
                stock_code = rows.get(excel_row, {}).get(2, "")  # B sütunu
                clean_code = clean_stock_code(stock_code)

                report_row: dict[str, object] = {
                    "sheet_name": sheet_name,
                    "drawing_xml": drawing_path,
                    "anchor_no": record["anchor_no"],
                    "excel_row": excel_row,
                    "excel_column": record["excel_column"],
                    "stock_code": stock_code,
                    "media_path": media_path,
                    "output_file": "",
                    "status": "",
                }

                if not clean_code:
                    missing_stock_count += 1
                    report_row["status"] = "stok_kodu_bos"
                    report_rows.append(report_row)
                    continue

                if media_path not in names:
                    missing_media_count += 1
                    report_row["status"] = "media_dosyasi_bulunamadi"
                    report_rows.append(report_row)
                    continue

                extension = PurePosixPath(media_path).suffix or ".bin"
                output_path = unique_output_path(
                    output_dir, clean_code, extension, counters
                )

                with zf.open(media_path) as source, output_path.open("wb") as target:
                    target.write(source.read())

                copied_count += 1
                report_row["output_file"] = output_path.name
                report_row["status"] = "kopyalandi"
                report_rows.append(report_row)

    except (zipfile.BadZipFile, ET.ParseError, ValueError, OSError) as exc:
        print(f"❌ İşlem durduruldu: {exc}")
        return 1

    fieldnames = [
        "sheet_name",
        "drawing_xml",
        "anchor_no",
        "excel_row",
        "excel_column",
        "stock_code",
        "media_path",
        "output_file",
        "status",
    ]

    with mapping_csv.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    print("")
    print("✅ İşlem tamamlandı.")
    print(f"   Kopyalanan görsel: {copied_count}")
    print(f"   Stok kodu boş olan anchor: {missing_stock_count}")
    print(f"   Bulunamayan medya: {missing_media_count}")
    print(f"   Görsel klasörü: {output_dir}")
    print(f"   Eşleme raporu: {mapping_csv}")
    print("")
    print("Excel dosyası değiştirilmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
