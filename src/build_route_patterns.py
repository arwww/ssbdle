from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
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

ROUTES_FILE = GTFS_DIR / "routes.txt"
TRIPS_FILE = GTFS_DIR / "trips.txt"
STOP_TIMES_FILE = GTFS_DIR / "stop_times.txt"

TRAVEL_STATIONS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

STOP_MAPPING_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stop_mapping.csv"
)

OUTPUT_PATTERNS_JSON = (
    PROJECT_ROOT
    / "output"
    / "route_patterns.json"
)

OUTPUT_ROUTES_JSON = (
    PROJECT_ROOT
    / "output"
    / "travel_routes.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "route_patterns_review.csv"
)


STOP_TIMES_CHUNK_SIZE = 500_000

ALLOWED_ROUTE_TYPES = {
    "3",      # Bus
    "109",    # S-Bahn
    "402",    # Stadtbahn
    "1400",   # Zacke / Seilbahn
}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(
            f"Datei wurde nicht gefunden:\n{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_routes() -> pd.DataFrame:
    if not ROUTES_FILE.exists():
        raise FileNotFoundError(
            f"routes.txt wurde nicht gefunden:\n{ROUTES_FILE}"
        )

    routes = pd.read_csv(
        ROUTES_FILE,
        dtype=str,
        low_memory=False,
    )

    required_columns = {
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
    }

    missing_columns = (
        required_columns
        - set(routes.columns)
    )

    if missing_columns:
        raise ValueError(
            "In routes.txt fehlen Spalten: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    routes = routes[
        routes["route_type"]
        .fillna("")
        .isin(ALLOWED_ROUTE_TYPES)
    ].copy()

    return routes


def load_trips(
    allowed_route_ids: set[str],
) -> pd.DataFrame:
    if not TRIPS_FILE.exists():
        raise FileNotFoundError(
            f"trips.txt wurde nicht gefunden:\n{TRIPS_FILE}"
        )

    trips = pd.read_csv(
        TRIPS_FILE,
        dtype=str,
        usecols=[
            "route_id",
            "trip_id",
            "trip_headsign",
            "direction_id",
        ],
        low_memory=False,
    )

    trips = trips[
        trips["route_id"].isin(
            allowed_route_ids
        )
    ].copy()

    trips["trip_id"] = (
        trips["trip_id"]
        .map(normalize_text)
    )

    trips["route_id"] = (
        trips["route_id"]
        .map(normalize_text)
    )

    trips["trip_headsign"] = (
        trips["trip_headsign"]
        .map(normalize_text)
    )

    trips["direction_id"] = (
        trips["direction_id"]
        .map(normalize_text)
    )

    return trips


def load_stop_mapping() -> dict[str, str]:
    if not STOP_MAPPING_FILE.exists():
        raise FileNotFoundError(
            "travel_stop_mapping.csv wurde nicht gefunden.\n"
            f"Erwarteter Pfad:\n{STOP_MAPPING_FILE}"
        )

    mapping = pd.read_csv(
        STOP_MAPPING_FILE,
        dtype=str,
        usecols=[
            "stop_id",
            "canonical_station_id",
        ],
        low_memory=False,
    )

    mapping = mapping.dropna(
        subset=[
            "stop_id",
            "canonical_station_id",
        ]
    )

    return dict(
        zip(
            mapping["stop_id"],
            mapping[
                "canonical_station_id"
            ],
        )
    )


def remove_consecutive_duplicates(
    station_ids: list[str],
) -> list[str]:
    cleaned: list[str] = []

    for station_id in station_ids:
        if (
            cleaned
            and cleaned[-1] == station_id
        ):
            continue

        cleaned.append(station_id)

    return cleaned


def create_pattern_hash(
    route_id: str,
    direction_id: str,
    station_ids: list[str],
) -> str:
    raw_value = "|".join(
        [
            route_id,
            direction_id,
            *station_ids,
        ]
    )

    return hashlib.sha1(
        raw_value.encode("utf-8")
    ).hexdigest()[:16]


def build_trip_stop_sequences(
    allowed_trip_ids: set[str],
    stop_mapping: dict[str, str],
) -> dict[str, list[str]]:
    trip_sequences: dict[
        str,
        list[
            tuple[int, str]
        ],
    ] = defaultdict(list)

    print(
        "\nLese stop_times.txt stückweise ein …"
    )

    chunk_number = 0
    relevant_rows = 0

    for chunk in pd.read_csv(
        STOP_TIMES_FILE,
        dtype=str,
        usecols=[
            "trip_id",
            "stop_id",
            "stop_sequence",
        ],
        chunksize=STOP_TIMES_CHUNK_SIZE,
        low_memory=False,
    ):
        chunk_number += 1

        chunk = chunk[
            chunk["trip_id"].isin(
                allowed_trip_ids
            )
        ].copy()

        if chunk.empty:
            print(
                f"- Chunk {chunk_number}: "
                "keine relevanten Zeilen"
            )
            continue

        chunk["canonical_station_id"] = (
            chunk["stop_id"].map(
                stop_mapping
            )
        )

        chunk = chunk.dropna(
            subset=[
                "canonical_station_id",
                "stop_sequence",
            ]
        )

        chunk["stop_sequence_numeric"] = (
            pd.to_numeric(
                chunk["stop_sequence"],
                errors="coerce",
            )
        )

        chunk = chunk.dropna(
            subset=[
                "stop_sequence_numeric"
            ]
        )

        relevant_rows += len(chunk)

        for row in chunk.itertuples(
            index=False
        ):
            trip_sequences[
                normalize_text(
                    row.trip_id
                )
            ].append(
                (
                    int(
                        row.stop_sequence_numeric
                    ),
                    normalize_text(
                        row.canonical_station_id
                    ),
                )
            )

        print(
            f"- Chunk {chunk_number}: "
            f"{len(chunk):,} relevante Zeilen"
        )

    print(
        f"\nRelevante Stop-Time-Zeilen: "
        f"{relevant_rows:,}"
    )

    final_sequences: dict[
        str,
        list[str],
    ] = {}

    for (
        trip_id,
        sequence_rows,
    ) in trip_sequences.items():
        ordered_station_ids = [
            station_id
            for _, station_id
            in sorted(
                sequence_rows,
                key=lambda item: item[0],
            )
        ]

        cleaned_station_ids = (
            remove_consecutive_duplicates(
                ordered_station_ids
            )
        )

        if len(cleaned_station_ids) < 2:
            continue

        final_sequences[
            trip_id
        ] = cleaned_station_ids

    return final_sequences


def build_patterns(
    trips: pd.DataFrame,
    trip_sequences: dict[
        str,
        list[str],
    ],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, list[str]],
]:
    pattern_occurrences: Counter[
        tuple[
            str,
            str,
            tuple[str, ...],
        ]
    ] = Counter()

    headsign_occurrences: dict[
        tuple[
            str,
            str,
            tuple[str, ...],
        ],
        Counter[str],
    ] = defaultdict(Counter)

    for row in trips.itertuples(
        index=False
    ):
        trip_id = normalize_text(
            row.trip_id
        )

        station_ids = (
            trip_sequences.get(
                trip_id
            )
        )

        if not station_ids:
            continue

        route_id = normalize_text(
            row.route_id
        )

        direction_id = normalize_text(
            row.direction_id
        )

        pattern_key = (
            route_id,
            direction_id,
            tuple(station_ids),
        )

        pattern_occurrences[
            pattern_key
        ] += 1

        trip_headsign = normalize_text(
            row.trip_headsign
        )

        if trip_headsign:
            headsign_occurrences[
                pattern_key
            ][
                trip_headsign
            ] += 1

    patterns: dict[
        str,
        dict[str, Any],
    ] = {}

    route_pattern_ids: dict[
        str,
        list[str],
    ] = defaultdict(list)

    for (
        pattern_key,
        trip_count,
    ) in pattern_occurrences.items():
        (
            route_id,
            direction_id,
            station_tuple,
        ) = pattern_key

        station_ids = list(
            station_tuple
        )

        pattern_hash = (
            create_pattern_hash(
                route_id,
                direction_id,
                station_ids,
            )
        )

        pattern_id = (
            f"pattern_{pattern_hash}"
        )

        headsign_counter = (
            headsign_occurrences.get(
                pattern_key,
                Counter(),
            )
        )

        headsign = (
            headsign_counter
            .most_common(1)[0][0]
            if headsign_counter
            else ""
        )

        patterns[
            pattern_id
        ] = {
            "id": pattern_id,
            "route_id": route_id,
            "direction_id": (
                direction_id
            ),
            "headsign": headsign,
            "station_ids": (
                station_ids
            ),
            "station_count": len(
                station_ids
            ),
            "trip_count": int(
                trip_count
            ),
        }

        route_pattern_ids[
            route_id
        ].append(
            pattern_id
        )

    for route_id in route_pattern_ids:
        route_pattern_ids[
            route_id
        ].sort(
            key=lambda pattern_id: (
                -patterns[
                    pattern_id
                ]["trip_count"],
                patterns[
                    pattern_id
                ]["headsign"],
            )
        )

    return (
        patterns,
        dict(route_pattern_ids),
    )


def build_routes_output(
    routes: pd.DataFrame,
    route_pattern_ids: dict[
        str,
        list[str],
    ],
) -> dict[str, dict[str, Any]]:
    output: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in routes.itertuples(
        index=False
    ):
        route_id = normalize_text(
            row.route_id
        )

        pattern_ids = (
            route_pattern_ids.get(
                route_id,
                [],
            )
        )

        if not pattern_ids:
            continue

        output[
            route_id
        ] = {
            "id": route_id,
            "short_name": (
                normalize_text(
                    row.route_short_name
                )
            ),
            "long_name": (
                normalize_text(
                    row.route_long_name
                )
            ),
            "route_type": (
                normalize_text(
                    row.route_type
                )
            ),
            "pattern_ids": (
                pattern_ids
            ),
            "pattern_count": len(
                pattern_ids
            ),
        }

    return output


def build_review_rows(
    patterns: dict[
        str,
        dict[str, Any],
    ],
    routes_output: dict[
        str,
        dict[str, Any],
    ],
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for pattern in patterns.values():
        route = routes_output.get(
            pattern["route_id"],
            {},
        )

        station_ids = (
            pattern["station_ids"]
        )

        station_names = [
            travel_stations
            .get(
                station_id,
                {},
            )
            .get(
                "name",
                station_id,
            )
            for station_id
            in station_ids
        ]

        rows.append(
            {
                "pattern_id": (
                    pattern["id"]
                ),
                "route_id": (
                    pattern[
                        "route_id"
                    ]
                ),
                "route_short_name": (
                    route.get(
                        "short_name",
                        "",
                    )
                ),
                "route_long_name": (
                    route.get(
                        "long_name",
                        "",
                    )
                ),
                "route_type": (
                    route.get(
                        "route_type",
                        "",
                    )
                ),
                "direction_id": (
                    pattern[
                        "direction_id"
                    ]
                ),
                "headsign": (
                    pattern[
                        "headsign"
                    ]
                ),
                "station_count": (
                    pattern[
                        "station_count"
                    ]
                ),
                "trip_count": (
                    pattern[
                        "trip_count"
                    ]
                ),
                "first_station": (
                    station_names[0]
                ),
                "last_station": (
                    station_names[-1]
                ),
                "station_sequence": (
                    " → ".join(
                        station_names
                    )
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row[
                "route_short_name"
            ],
            row[
                "direction_id"
            ],
            -row[
                "trip_count"
            ],
        )
    )

    return rows


def save_json(
    path: Path,
    data: Any,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def print_examples(
    routes_output: dict[
        str,
        dict[str, Any],
    ],
    patterns: dict[
        str,
        dict[str, Any],
    ],
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    example_lines = [
        "S1",
        "U1",
        "U6",
        "42",
        "10",
    ]

    print("\nBeispiele:")

    for line_name in example_lines:
        matching_routes = [
            route
            for route
            in routes_output.values()
            if route[
                "short_name"
            ] == line_name
        ]

        print(
            f"\nLinie {line_name}:"
        )

        if not matching_routes:
            print(
                "- keine Route gefunden"
            )
            continue

        for route in matching_routes:
            for pattern_id in (
                route[
                    "pattern_ids"
                ][:3]
            ):
                pattern = patterns[
                    pattern_id
                ]

                station_names = [
                    travel_stations
                    .get(
                        station_id,
                        {},
                    )
                    .get(
                        "name",
                        station_id,
                    )
                    for station_id
                    in pattern[
                        "station_ids"
                    ]
                ]

                preview = (
                    " → ".join(
                        station_names[:8]
                    )
                )

                if (
                    len(station_names) > 8
                ):
                    preview += " → …"

                print(
                    "- "
                    f"{pattern['headsign']} | "
                    f"{pattern['station_count']} Stationen | "
                    f"{pattern['trip_count']} Fahrten\n"
                    f"  {preview}"
                )


def main() -> None:
    routes = load_routes()

    allowed_route_ids = set(
        routes["route_id"]
        .map(normalize_text)
    )

    trips = load_trips(
        allowed_route_ids
    )

    stop_mapping = (
        load_stop_mapping()
    )

    travel_stations = (
        load_json(
            TRAVEL_STATIONS_FILE
        )
    )

    trip_sequences = (
        build_trip_stop_sequences(
            set(
                trips["trip_id"]
            ),
            stop_mapping,
        )
    )

    (
        patterns,
        route_pattern_ids,
    ) = build_patterns(
        trips,
        trip_sequences,
    )

    routes_output = (
        build_routes_output(
            routes,
            route_pattern_ids,
        )
    )

    review_rows = (
        build_review_rows(
            patterns,
            routes_output,
            travel_stations,
        )
    )

    save_json(
        OUTPUT_PATTERNS_JSON,
        patterns,
    )

    save_json(
        OUTPUT_ROUTES_JSON,
        routes_output,
    )

    pd.DataFrame(
        review_rows
    ).to_csv(
        OUTPUT_REVIEW_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 72)
    print("ROUTE-PATTERNS ERFOLGREICH ERSTELLT")
    print("=" * 72)

    print(
        f"Berücksichtigte Linien: "
        f"{len(routes_output):,}"
    )

    print(
        f"Berücksichtigte Fahrten: "
        f"{len(trip_sequences):,}"
    )

    print(
        f"Eindeutige Route-Patterns: "
        f"{len(patterns):,}"
    )

    print(
        "\nRoute-Patterns:\n"
        f"{OUTPUT_PATTERNS_JSON}"
    )

    print(
        "\nTravel-Routen:\n"
        f"{OUTPUT_ROUTES_JSON}"
    )

    print(
        "\nKontroll-CSV:\n"
        f"{OUTPUT_REVIEW_CSV}"
    )

    print_examples(
        routes_output,
        patterns,
        travel_stations,
    )


if __name__ == "__main__":
    main()