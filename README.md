# KSeF PDF Renamer

Lokalna aplikacja web oraz narzędzie CLI do zmiany nazw faktur PDF pobranych z KSeF.
Docelowy schemat nazwy pliku:

```text
data wystawienia_nr faktury_sprzedawca_nazwa towaru.pdf
```

Aplikacja odczytuje warstwę tekstową PDF i rozpoznaje:

- datę wystawienia,
- numer faktury,
- nazwę sprzedawcy,
- pierwszą nazwę towaru lub usługi z tabeli pozycji.

> Uwaga: jeżeli PDF jest skanem bez tekstu, przed użyciem narzędzia potrzebny jest OCR.

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Aplikacja web

```bash
flask --app ksef_pdf_renamer.app run
```

Następnie otwórz `http://127.0.0.1:5000`, dodaj jeden lub wiele plików PDF i wybierz:

- **Podejrzyj nazwy** — pokazuje planowane nazwy bez pobierania plików,
- **Pobierz ZIP ze zmienionymi nazwami** — zwraca archiwum ZIP z plikami pod nowymi nazwami.

## CLI

Podejrzenie planowanych zmian:

```bash
ksef-pdf-renamer --dry-run faktura.pdf
```

Zmiana nazwy obok oryginalnego pliku:

```bash
ksef-pdf-renamer faktura.pdf
```

Skopiowanie plików do osobnego katalogu:

```bash
ksef-pdf-renamer --copy --output-dir renamed *.pdf
```
