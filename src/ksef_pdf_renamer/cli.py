from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .extractor import ensure_unique_filename, extract_invoice_data, make_target_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Zmieniaj nazwy faktur PDF pobranych z KSeF.")
    parser.add_argument("pdf", nargs="+", type=Path, help="Pliki PDF do przetworzenia")
    parser.add_argument("--output-dir", "-o", type=Path, help="Katalog docelowy. Domyślnie zmienia nazwę obok pliku.")
    parser.add_argument("--copy", action="store_true", help="Kopiuj pliki zamiast przenosić/zmieniać nazwę.")
    parser.add_argument("--dry-run", action="store_true", help="Pokaż plan bez modyfikowania plików.")
    args = parser.parse_args()

    used_names: set[str] = set()
    for pdf_path in args.pdf:
        try:
            data = extract_invoice_data(pdf_path)
            target_name = ensure_unique_filename(make_target_filename(data), used_names)
            used_names.add(target_name)
            target_dir = args.output_dir or pdf_path.parent
            target_path = target_dir / target_name
            print(f"{pdf_path} -> {target_path}")
            if args.dry_run:
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            if args.copy:
                shutil.copy2(pdf_path, target_path)
            else:
                pdf_path.rename(target_path)
        except Exception as exc:  # noqa: BLE001 - CLI should continue with next file
            print(f"BŁĄD: {pdf_path}: {exc}")


if __name__ == "__main__":
    main()
