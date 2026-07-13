from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = PROJECT_ROOT / "output" / "stations_all.json"

OUTPUT_JSON = PROJECT_ROOT / "output" / "stations_game.json"
OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT / "output" / "stations_game_review.csv"
)


# Bei diesen Städten werden nur größere Haltestellen übernommen.
SURROUNDING_CITY_TERMS = {
    "esslingen",
    "boblingen",
    "sindelfingen",
    "ludwigsburg",
    "fellbach",
    "waiblingen",
    "leonberg",
    "filderstadt",
    "leinfelden-echterdingen",
}


# Verkehrsmittel, die eine Haltestelle automatisch relevant machen.
RAIL_MODES = {
    "s-bahn",
    "r-bahn",
    "regionalbahn",
    "stadtbahn",
    "zahnradbahn",
    "seilbahn",
}


MAIN_STATION_KEYWORDS = {
    "hauptbahnhof",
    "bahnhof",
    "zob",
    "zentrum",
}


MINIMUM_LINES_FOR_MAJOR_STOP = 5


# Hier können wir später einzelne Stationen erzwingen.
# Format: ("Gemeinde", "Haltestellenname")
MANUAL_INCLUDE: set[tuple[str, str]] = set()


# Hier können wir später störende Stationen ausschließen.
MANUAL_EXCLUDE: set[tuple[str, str]] = set()


def normalize_text(value: Any) -> str:
    """
    Vereinheitlicht Texte für Vergleiche.

    Beispiel:
    Böblingen -> boblingen
    """

    text = str(value or "").strip().casefold()

    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def station_key(station: dict[str, Any]) -> tuple[str, str]:
    """Erzeugt einen eindeutigen Vergleichsschlüssel."""

    return (
        normalize_text(station.get("municipality")),
        normalize_text(station.get("name")),
    )


NORMALIZED_MANUAL_INCLUDE = {
    (
        normalize_text(municipality),
        normalize_text(name),
    )
    for municipality, name in MANUAL_INCLUDE
}

NORMALIZED_MANUAL_EXCLUDE = {
    (
        normalize_text(municipality),
        normalize_text(name),
    )
    for municipality, name in MANUAL_EXCLUDE
}


def load_stations() -> list[dict[str, Any]]:
    """Lädt die zuvor aufbereiteten Haltestellen."""

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "Die Datei stations_all.json wurde nicht gefunden.\n"
            f"Erwarteter Pfad:\n{INPUT_FILE}\n\n"
            "Führe zuerst build_stations.py aus."
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            "stations_all.json muss eine Liste enthalten."
        )

    return data


def is_surrounding_city(municipality: str) -> bool:
    """Prüft, ob die Gemeinde zu unserem Umland-Pool gehört."""

    normalized = normalize_text(municipality)

    return any(
        city_term in normalized
        for city_term in SURROUNDING_CITY_TERMS
    )


def has_rail_transport(station: dict[str, Any]) -> bool:
    """Prüft, ob ein Bahnverkehrsmittel vorhanden ist."""

    modes = {
        normalize_text(mode)
        for mode in station.get("modes", [])
    }

    return bool(modes & RAIL_MODES)


def contains_main_station_keyword(
    station: dict[str, Any],
) -> bool:
    """Sucht nach Begriffen wie Bahnhof oder ZOB."""

    searchable_name = normalize_text(
        station.get("name_with_place")
        or station.get("name")
    )

    return any(
        keyword in searchable_name
        for keyword in MAIN_STATION_KEYWORDS
    )


def get_line_count(station: dict[str, Any]) -> int:
    """Liest die Linienzahl robust aus."""

    value = station.get("line_count")

    try:
        return int(value)
    except (TypeError, ValueError):
        return len(station.get("lines", []))


def determine_selection_reason(
    station: dict[str, Any],
) -> str | None:
    """
    Gibt den Aufnahmegrund zurück.

    None bedeutet: Station wird nicht aufgenommen.
    """

    key = station_key(station)

    if key in NORMALIZED_MANUAL_EXCLUDE:
        return None

    if key in NORMALIZED_MANUAL_INCLUDE:
        return "manual_include"

    municipality = normalize_text(
        station.get("municipality")
    )

    # Alle Stuttgarter Haltestellen übernehmen.
    if municipality == "stuttgart":
        return "stuttgart"

    # Andere Orte außerhalb des gewählten Umlands ausschließen.
    if not is_surrounding_city(municipality):
        return None

    line_count = get_line_count(station)

    if has_rail_transport(station):
        return "surrounding_city_rail"

    if line_count >= MINIMUM_LINES_FOR_MAJOR_STOP:
        return "surrounding_city_many_lines"

    if (
        contains_main_station_keyword(station)
        and line_count >= 2
    ):
        return "surrounding_city_keyword"

    return None


def build_game_pool(
    stations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Erzeugt den Spielpool und eine Prüftabelle."""

    game_stations: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for station in stations:
        reason = determine_selection_reason(station)

        if reason is None:
            continue

        game_stations.append(station)

        review_rows.append(
            {
                "id": station.get("id"),
                "name": station.get("name"),
                "municipality": station.get("municipality"),
                "locality": station.get("locality"),
                "modes": "; ".join(
                    station.get("modes", [])
                ),
                "lines": ", ".join(
                    station.get("lines", [])
                ),
                "line_count": get_line_count(station),
                "selection_reason": reason,
            }
        )

    game_stations.sort(
        key=lambda station: (
            normalize_text(station.get("municipality")),
            normalize_text(station.get("name")),
        )
    )

    review_rows.sort(
        key=lambda row: (
            normalize_text(row["municipality"]),
            normalize_text(row["name"]),
        )
    )

    return game_stations, review_rows


def save_results(
    game_stations: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    """Speichert JSON und Kontroll-CSV."""

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            game_stations,
            file,
            ensure_ascii=False,
            indent=2,
        )

    pd.DataFrame(review_rows).to_csv(
        OUTPUT_REVIEW_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def print_summary(
    stations: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    """Zeigt eine verständliche Zusammenfassung."""

    review_dataframe = pd.DataFrame(review_rows)

    print("=" * 60)
    print("SPIELPOOL ERFOLGREICH ERSTELLT")
    print("=" * 60)

    print(f"Haltestellen vorher: {len(stations):,}")
    print(f"Haltestellen im Spielpool: {len(review_rows):,}")

    if not review_dataframe.empty:
        print("\nHaltestellen nach Gemeinde:")

        municipality_counts = (
            review_dataframe["municipality"]
            .value_counts()
            .sort_index()
        )

        print(municipality_counts.to_string())

        print("\nAufnahmegründe:")

        reason_counts = (
            review_dataframe["selection_reason"]
            .value_counts()
        )

        print(reason_counts.to_string())

    print(f"\nSpiel-JSON:\n{OUTPUT_JSON}")
    print(f"\nKontroll-CSV:\n{OUTPUT_REVIEW_CSV}")


def main() -> None:
    stations = load_stations()

    game_stations, review_rows = build_game_pool(
        stations
    )

    save_results(
        game_stations,
        review_rows,
    )

    print_summary(
        stations,
        review_rows,
    )


if __name__ == "__main__":
    main()