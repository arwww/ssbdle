from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GTFS_DIR = (
    PROJECT_ROOT
    / "data"
    / "gtfs-vvs"
    / "realtime"
)

STOPS_FILE = GTFS_DIR / "stops.txt"

OUTPUT_JSON = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

OUTPUT_MAPPING_CSV = (
    PROJECT_ROOT
    / "output"
    / "travel_stop_mapping.csv"
)




def normalize_text(value: Any) -> str:
    """
    Wandelt Werte sicher in Text um.

    Pandas-NaN-Werte werden als leer behandelt,
    damit sie nicht versehentlich zur Zeichenfolge
    'nan' werden.
    """

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def derive_base_station_id(stop_id: str) -> str:
    """
    Leitet aus einer Bahnsteig- oder Haltepunkt-ID
    die gemeinsame logische Stations-ID ab.

    Beispiele:
    de:08111:6019:1:2   -> de:08111:6019
    de:08111:6118:1:101 -> de:08111:6118
    de:08116:2800:0:3   -> de:08116:2800
    """

    parts = stop_id.split(":")

    if len(parts) >= 3:
        return ":".join(parts[:3])

    return stop_id


def determine_canonical_station_id(
    row: pd.Series,
) -> str:
    parent_station = normalize_text(
        row.get("parent_station")
    )

    stop_id = normalize_text(
        row.get("stop_id")
    )

    if parent_station:
        return parent_station

    return derive_base_station_id(
        stop_id
    )


def load_stops() -> pd.DataFrame:
    if not STOPS_FILE.exists():
        raise FileNotFoundError(
            f"stops.txt wurde nicht gefunden:\n{STOPS_FILE}"
        )

    stops = pd.read_csv(
        STOPS_FILE,
        dtype=str,
        low_memory=False,
    )

    required_columns = {
        "stop_id",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "location_type",
        "parent_station",
    }

    missing_columns = (
        required_columns
        - set(stops.columns)
    )

    if missing_columns:
        raise ValueError(
            "Folgende Spalten fehlen in stops.txt: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    return stops


def choose_station_name(
    group: pd.DataFrame,
) -> str:
    """
    Bevorzugt den Namen eines location_type=1-Eintrags.
    Falls keiner vorhanden ist, wird der häufigste Name genutzt.
    """

    station_rows = group[
        group["location_type"]
        .fillna("")
        .astype(str)
        .eq("1")
    ]

    if not station_rows.empty:
        name = normalize_text(
            station_rows.iloc[0]["stop_name"]
        )

        if name:
            return name

    names = (
        group["stop_name"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    names = names[
        names.ne("")
    ]

    if names.empty:
        return "Unbekannte Station"

    return (
        names.value_counts()
        .index[0]
    )


def calculate_mean_coordinate(
    values: pd.Series,
) -> float | None:
    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return None

    return float(
        numeric_values.mean()
    )


def build_station_groups(
    stops: pd.DataFrame,
) -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    stops = stops.copy()

    stops["canonical_station_id"] = (
        stops.apply(
            determine_canonical_station_id,
            axis=1,
        )
    )

    travel_stations: dict[
        str,
        dict[str, Any],
    ] = {}

    mapping_rows: list[
        dict[str, Any]
    ] = []

    grouped = stops.groupby(
        "canonical_station_id",
        sort=True,
        dropna=False,
    )

    for (
        canonical_station_id,
        group,
    ) in grouped:
        canonical_station_id = (
            normalize_text(
                canonical_station_id
            )
        )

        if not canonical_station_id:
            continue

        station_name = (
            choose_station_name(
                group
            )
        )

        latitude = (
            calculate_mean_coordinate(
                group["stop_lat"]
            )
        )

        longitude = (
            calculate_mean_coordinate(
                group["stop_lon"]
            )
        )

        platform_stop_ids = sorted(
            {
                normalize_text(stop_id)
                for stop_id
                in group["stop_id"]
                if normalize_text(
                    stop_id
                )
            }
        )

        parent_station_ids = sorted(
            {
                normalize_text(
                    parent_station
                )
                for parent_station
                in group[
                    "parent_station"
                ]
                if normalize_text(
                    parent_station
                )
            }
        )

        location_types = sorted(
            {
                normalize_text(
                    location_type
                )
                for location_type
                in group[
                    "location_type"
                ]
                if normalize_text(
                    location_type
                )
            }
        )

        travel_stations[
            canonical_station_id
        ] = {
            "id": canonical_station_id,
            "name": station_name,
            "latitude": latitude,
            "longitude": longitude,
            "platform_stop_ids": (
                platform_stop_ids
            ),
            "platform_count": len(
                platform_stop_ids
            ),
            "parent_station_ids": (
                parent_station_ids
            ),
            "location_types": (
                location_types
            ),
        }

        for _, row in group.iterrows():
            mapping_rows.append(
                {
                    "stop_id": normalize_text(
                        row.get("stop_id")
                    ),
                    "stop_name": normalize_text(
                        row.get("stop_name")
                    ),
                    "canonical_station_id": (
                        canonical_station_id
                    ),
                    "canonical_station_name": (
                        station_name
                    ),
                    "parent_station": (
                        normalize_text(
                            row.get(
                                "parent_station"
                            )
                        )
                    ),
                    "location_type": (
                        normalize_text(
                            row.get(
                                "location_type"
                            )
                        )
                    ),
                    "stop_lat": normalize_text(
                        row.get("stop_lat")
                    ),
                    "stop_lon": normalize_text(
                        row.get("stop_lon")
                    ),
                }
            )

    return (
        travel_stations,
        mapping_rows,
    )


def validate_results(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    mapping_rows: list[
        dict[str, Any]
    ],
) -> None:
    if not travel_stations:
        raise ValueError(
            "Es wurden keine Travel-Stationen erzeugt."
        )

    mapped_stop_ids = {
        row["stop_id"]
        for row in mapping_rows
        if row["stop_id"]
    }

    if not mapped_stop_ids:
        raise ValueError(
            "Es wurden keine Stop-IDs zugeordnet."
        )

    for (
        station_id,
        station,
    ) in travel_stations.items():
        if not station["platform_stop_ids"]:
            raise ValueError(
                f"Station {station_id} enthält keine Stop-IDs."
            )


def save_results(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    mapping_rows: list[
        dict[str, Any]
    ],
) -> None:
    OUTPUT_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            travel_stations,
            file,
            ensure_ascii=False,
            indent=2,
        )

    pd.DataFrame(
        mapping_rows
    ).to_csv(
        OUTPUT_MAPPING_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def print_examples(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    search_terms = [
        "Marienplatz",
        "Vaihingen",
        "Esslingen",
        "Hauptbahnhof",
    ]

    print("\nBeispiele:")

    for search_term in search_terms:
        matches = [
            station
            for station
            in travel_stations.values()
            if search_term.casefold()
            in station["name"].casefold()
        ]

        print(
            f"\nTreffer für „{search_term}“:"
        )

        for station in matches[:10]:
            print(
                "- "
                f"{station['id']} | "
                f"{station['name']} | "
                f"{station['platform_count']} Stop-IDs"
            )


def print_summary(
    stops: pd.DataFrame,
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    mapping_rows: list[
        dict[str, Any]
    ],
) -> None:
    print("=" * 72)
    print("TRAVEL-STATIONEN ERFOLGREICH ERSTELLT")
    print("=" * 72)

    print(
        f"GTFS-Stop-Datensätze:       "
        f"{len(stops):,}"
    )

    print(
        f"Logische Travel-Stationen: "
        f"{len(travel_stations):,}"
    )

    print(
        f"Zuordnungen Stop → Station: "
        f"{len(mapping_rows):,}"
    )

    print(
        "\nTravel-Stationen:\n"
        f"{OUTPUT_JSON}"
    )

    print(
        "\nKontroll-Mapping:\n"
        f"{OUTPUT_MAPPING_CSV}"
    )

    print_examples(
        travel_stations
    )


def main() -> None:
    stops = load_stops()

    (
        travel_stations,
        mapping_rows,
    ) = build_station_groups(
        stops
    )

    validate_results(
        travel_stations,
        mapping_rows,
    )

    save_results(
        travel_stations,
        mapping_rows,
    )

    print_summary(
        stops,
        travel_stations,
        mapping_rows,
    )


if __name__ == "__main__":
    main()