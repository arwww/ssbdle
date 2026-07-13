from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "output"
    / "stations_game.json"
)

OUTPUT_JSON = (
    PROJECT_ROOT
    / "output"
    / "stations_answers.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "stations_answers_review.csv"
)


RAIL_MODES = {
    "stadtbahn",
    "s-bahn",
    "r-bahn",
    "regionalbahn",
    "zahnradbahn",
    "seilbahn",
}


IMPORTANT_KEYWORDS = {
    "hauptbahnhof",
    "bahnhof",
    "zob",
    "zentrum",
    "rathaus",
    "universitat",
    "flughafen",
    "messe",
}


# Mindestanzahl normaler Linien
MIN_STUTTGART_LINES = 3
MIN_SURROUNDING_LINES = 6


# Einzelne Stationen können später gezielt ergänzt werden.
# Format: ("Gemeinde", "Name")
MANUAL_INCLUDE: set[tuple[str, str]] = {
    # ("Stuttgart", "Beispielhaltestelle"),
}


# Einzelne störende Stationen können gezielt entfernt werden.
MANUAL_EXCLUDE: set[tuple[str, str]] = {
    # ("Stuttgart", "Beispielhaltestelle"),
}


def normalize_text(value: Any) -> str:
    """
    Vereinheitlicht Texte für sichere Vergleiche.

    Beispiele:
    Universität -> universitat
    Böblingen -> boblingen
    """

    text = str(value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def station_key(
    station: dict[str, Any],
) -> tuple[str, str]:
    return (
        normalize_text(station.get("municipality")),
        normalize_text(station.get("name")),
    )


NORMALIZED_INCLUDE = {
    (
        normalize_text(municipality),
        normalize_text(name),
    )
    for municipality, name in MANUAL_INCLUDE
}


NORMALIZED_EXCLUDE = {
    (
        normalize_text(municipality),
        normalize_text(name),
    )
    for municipality, name in MANUAL_EXCLUDE
}


def load_stations() -> list[dict[str, Any]]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "stations_game.json wurde nicht gefunden.\n"
            f"Erwarteter Pfad:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        stations = json.load(file)

    if not isinstance(stations, list):
        raise ValueError(
            "stations_game.json muss eine Liste enthalten."
        )

    return stations


def has_rail(station: dict[str, Any]) -> bool:
    modes = {
        normalize_text(mode)
        for mode in station.get("modes", [])
    }

    return bool(modes & RAIL_MODES)


def is_weak_mode_only(
    station: dict[str, Any],
) -> bool:
    """
    Entfernt Stationen, die ausschließlich Nachtbus,
    Ruftaxi oder Ersatzverkehr besitzen.
    """

    modes = {
        normalize_text(mode)
        for mode in station.get("modes", [])
    }

    weak_modes = {
        "nachtbus",
        "ruftaxi",
        "sev-bus",
    }

    return bool(modes) and modes.issubset(weak_modes)


def count_relevant_lines(
    station: dict[str, Any],
) -> int:
    """
    Zählt Linien ohne reine Nacht- und SEV-Linien.

    Dadurch wird eine Station nicht nur wegen mehrerer
    Nacht- oder Ersatzlinien als besonders wichtig eingestuft.
    """

    relevant_lines: list[str] = []

    for line in station.get("lines", []):
        line_text = str(line).strip()
        normalized = normalize_text(line_text)

        if not normalized:
            continue

        if normalized.startswith("sev"):
            continue

        # N1, N2, N10 usw. gelten als Nachtlinien.
        if (
            normalized.startswith("n")
            and normalized[1:].isdigit()
        ):
            continue

        relevant_lines.append(line_text)

    return len(set(relevant_lines))


def has_important_keyword(
    station: dict[str, Any],
) -> bool:
    searchable_text = normalize_text(
        " ".join(
            [
                str(station.get("name", "")),
                str(station.get("name_with_place", "")),
            ]
        )
    )

    return any(
        keyword in searchable_text
        for keyword in IMPORTANT_KEYWORDS
    )


def determine_answer_reason(
    station: dict[str, Any],
) -> str | None:
    key = station_key(station)

    if key in NORMALIZED_EXCLUDE:
        return None

    if key in NORMALIZED_INCLUDE:
        return "manual_include"

    if is_weak_mode_only(station):
        return None

    municipality = normalize_text(
        station.get("municipality")
    )

    relevant_line_count = count_relevant_lines(
        station
    )

    rail = has_rail(station)
    keyword = has_important_keyword(station)

    # Stuttgart: Bahnstationen oder größere Bushaltestellen.
    if municipality == "stuttgart":
        if rail:
            return "stuttgart_rail"

        if relevant_line_count >= MIN_STUTTGART_LINES:
            return "stuttgart_many_lines"

        if keyword and relevant_line_count >= 2:
            return "stuttgart_keyword"

        return None

    # Umland: deutlich strengere Auswahl.
    if rail:
        return "surrounding_rail"

    if relevant_line_count >= MIN_SURROUNDING_LINES:
        return "surrounding_many_lines"

    if keyword and relevant_line_count >= 3:
        return "surrounding_keyword"

    return None


def build_answer_pool(
    stations: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    answers: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    seen_ids: set[str] = set()

    for station in stations:
        reason = determine_answer_reason(station)

        if reason is None:
            continue

        station_id = str(
            station.get("id", "")
        ).strip()

        if not station_id:
            continue

        if station_id in seen_ids:
            continue

        seen_ids.add(station_id)
        answers.append(station)

        review_rows.append(
            {
                "id": station_id,
                "name": station.get("name", ""),
                "name_with_place": station.get(
                    "name_with_place",
                    "",
                ),
                "municipality": station.get(
                    "municipality",
                    "",
                ),
                "locality": station.get(
                    "locality",
                    "",
                ),
                "modes": "; ".join(
                    station.get("modes", [])
                ),
                "lines": ", ".join(
                    station.get("lines", [])
                ),
                "original_line_count": station.get(
                    "line_count",
                    0,
                ),
                "relevant_line_count": (
                    count_relevant_lines(station)
                ),
                "answer_reason": reason,
            }
        )

    answers.sort(
        key=lambda station: (
            normalize_text(
                station.get("municipality")
            ),
            normalize_text(
                station.get("name")
            ),
        )
    )

    review_rows.sort(
        key=lambda row: (
            normalize_text(row["municipality"]),
            normalize_text(row["name"]),
        )
    )

    return answers, review_rows


def save_results(
    answers: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            answers,
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
    input_stations: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    dataframe = pd.DataFrame(review_rows)

    print("=" * 60)
    print("LÖSUNGSPOOL ERFOLGREICH ERSTELLT")
    print("=" * 60)

    print(
        f"Stationen im Eingabepool: "
        f"{len(input_stations):,}"
    )

    print(
        f"Stationen im Lösungspool: "
        f"{len(review_rows):,}"
    )

    if not dataframe.empty:
        print("\nLösungen nach Gemeinde:")

        print(
            dataframe["municipality"]
            .value_counts()
            .sort_index()
            .to_string()
        )

        print("\nAufnahmegründe:")

        print(
            dataframe["answer_reason"]
            .value_counts()
            .to_string()
        )

        duplicate_rows = dataframe[
            dataframe.duplicated(
                subset=["name"],
                keep=False,
            )
        ]

        print(
            "\nZeilen mit mehrfach vorkommendem Namen: "
            f"{len(duplicate_rows):,}"
        )

    print(f"\nLösungs-JSON:\n{OUTPUT_JSON}")
    print(f"\nKontroll-CSV:\n{OUTPUT_REVIEW_CSV}")


def main() -> None:
    stations = load_stations()

    answers, review_rows = build_answer_pool(
        stations
    )

    save_results(
        answers,
        review_rows,
    )

    print_summary(
        stations,
        review_rows,
    )


if __name__ == "__main__":
    main()