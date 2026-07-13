from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "haltestellen-vvs"
    / "vvs_haltestelle_j26.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "output"

OUTPUT_JSON = OUTPUT_DIR / "stations_all.json"
OUTPUT_CSV = OUTPUT_DIR / "stations_all.csv"


REQUIRED_COLUMNS = [
    "Name",
    "Name mit Ort",
    "Globale ID",
    "Gemeinde",
    "Teilort",
    "Landkreis",
    "Tarifzonen",
    "Verkehrsmittel",
    "Linien (EFA)",
    "Anzahl Linien",
    "X-Koordinate",
    "Y-Koordinate",
]


def read_source_file(path: Path) -> pd.DataFrame:
    """Liest die offizielle VVS-Haltestellen-CSV."""

    if not path.exists():
        raise FileNotFoundError(
            f"Die Quelldatei wurde nicht gefunden:\n{path}"
        )

    return pd.read_csv(
        path,
        sep=None,
        engine="python",
        encoding="cp1252",
        dtype=str,
    )


def clean_text(value: Any) -> str:
    """Entfernt Leerzeichen und wandelt fehlende Werte in Text um."""

    if pd.isna(value):
        return ""

    return str(value).strip()


def split_unique(value: Any, separator: str) -> list[str]:
    """
    Teilt eine Textspalte in eine Liste auf und entfernt
    leere oder doppelte Werte.
    """

    text = clean_text(value)

    if not text:
        return []

    values = [
        part.strip()
        for part in text.split(separator)
        if part.strip()
    ]

    # Entfernt Duplikate und erhält die ursprüngliche Reihenfolge.
    return list(dict.fromkeys(values))


def parse_german_float(value: Any) -> float | None:
    """
    Wandelt beispielsweise '9,1436295' in 9.1436295 um.
    """

    text = clean_text(value)

    if not text:
        return None

    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def build_station_records(
    dataframe: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Erzeugt die bereinigten Stationsobjekte."""

    records: list[dict[str, Any]] = []

    for row in dataframe.to_dict(orient="records"):
        lines = split_unique(
            row["Linien (EFA)"],
            separator=",",
        )

        modes = split_unique(
            row["Verkehrsmittel"],
            separator=";",
        )

        tariff_zones = split_unique(
            row["Tarifzonen"],
            separator=",",
        )

        longitude = parse_german_float(
            row["X-Koordinate"]
        )

        latitude = parse_german_float(
            row["Y-Koordinate"]
        )

        station = {
            "id": clean_text(row["Globale ID"]),
            "name": clean_text(row["Name"]),
            "name_with_place": clean_text(
                row["Name mit Ort"]
            ),
            "municipality": clean_text(
                row["Gemeinde"]
            ),
            "locality": clean_text(
                row["Teilort"]
            ),
            "county": clean_text(
                row["Landkreis"]
            ),
            "tariff_zones": tariff_zones,
            "modes": modes,
            "lines": lines,
            "line_count": len(lines),
            "longitude": longitude,
            "latitude": latitude,
        }

        # Unbrauchbare Datensätze werden nicht übernommen.
        if not station["id"]:
            continue

        if not station["name"]:
            continue

        if longitude is None or latitude is None:
            continue

        records.append(station)

    records.sort(
        key=lambda station: (
            station["name"].casefold(),
            station["municipality"].casefold(),
        )
    )

    return records


def save_json(
    records: list[dict[str, Any]],
) -> None:
    """Speichert die fertigen Stationsdaten als JSON."""

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            records,
            file,
            ensure_ascii=False,
            indent=2,
        )


def save_csv(
    records: list[dict[str, Any]],
) -> None:
    """
    Speichert zusätzlich eine CSV-Version,
    damit die Daten leicht kontrolliert werden können.
    """

    csv_records = []

    for station in records:
        csv_records.append(
            {
                **station,
                "tariff_zones": ", ".join(
                    station["tariff_zones"]
                ),
                "modes": "; ".join(
                    station["modes"]
                ),
                "lines": ", ".join(
                    station["lines"]
                ),
            }
        )

    pd.DataFrame(csv_records).to_csv(
        OUTPUT_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Lese Quelldatei:\n{INPUT_FILE}\n")

    dataframe = read_source_file(INPUT_FILE)

    dataframe.columns = [
        column.strip()
        for column in dataframe.columns
    ]

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Folgende benötigte Spalten fehlen:\n"
            + "\n".join(missing_columns)
        )

    records = build_station_records(dataframe)

    save_json(records)
    save_csv(records)

    unique_names = len(
        {
            station["name"].casefold()
            for station in records
        }
    )

    print("=" * 60)
    print("AUFBEREITUNG ERFOLGREICH")
    print("=" * 60)
    print(f"Quelldatensätze:       {len(dataframe):,}")
    print(f"Übernommene Stationen: {len(records):,}")
    print(f"Eindeutige Namen:      {unique_names:,}")
    print()
    print(f"JSON: {OUTPUT_JSON}")
    print(f"CSV:  {OUTPUT_CSV}")

    if records:
        print("\nBeispielstation:")
        print(
            json.dumps(
                records[0],
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()