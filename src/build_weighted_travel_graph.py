from __future__ import annotations

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

TRIPS_FILE = (
    GTFS_DIR
    / "trips.txt"
)

STOP_TIMES_FILE = (
    GTFS_DIR
    / "stop_times.txt"
)

STOP_MAPPING_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stop_mapping.csv"
)

TRAVEL_STATIONS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

TRAVEL_GRAPH_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_graph.json"
)

TRAVEL_TRANSFERS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_transfers.json"
)

OUTPUT_WEIGHTED_GRAPH_JSON = (
    PROJECT_ROOT
    / "output"
    / "weighted_travel_graph.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "weighted_travel_graph_review.csv"
)


# Ersatzwerte werden nur verwendet, wenn für eine Kante
# keine plausible Fahrzeit aus stop_times.txt gefunden wird.
DEFAULT_RIDE_TIMES_SECONDS = {
    "3": 120,       # Bus
    "109": 180,     # S-Bahn
    "402": 90,      # Stadtbahn
    "1400": 120,    # Sonder-/Zahnradbahn
}

DEFAULT_RIDE_TIME_SECONDS = 120

MIN_VALID_RIDE_TIME_SECONDS = 5
MAX_VALID_RIDE_TIME_SECONDS = 7200


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


def parse_gtfs_time(
    value: Any,
    cache: dict[str, int | None],
) -> int | None:
    """
    Wandelt GTFS-Zeiten in Sekunden um.

    GTFS erlaubt auch Uhrzeiten wie 25:17:00.
    Deshalb wird nicht datetime verwendet.
    """

    text = normalize_text(value)

    if not text:
        return None

    if text in cache:
        return cache[text]

    parts = text.split(":")

    if len(parts) != 3:
        cache[text] = None
        return None

    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
    except ValueError:
        cache[text] = None
        return None

    if (
        hours < 0
        or minutes < 0
        or minutes > 59
        or seconds < 0
        or seconds > 59
    ):
        cache[text] = None
        return None

    total_seconds = (
        hours * 3600
        + minutes * 60
        + seconds
    )

    cache[text] = total_seconds

    return total_seconds


def load_stop_mapping() -> dict[str, str]:
    if not STOP_MAPPING_FILE.exists():
        raise FileNotFoundError(
            "Stop-Mapping wurde nicht gefunden:\n"
            f"{STOP_MAPPING_FILE}"
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

    mapping["stop_id"] = (
        mapping["stop_id"]
        .map(normalize_text)
    )

    mapping["canonical_station_id"] = (
        mapping["canonical_station_id"]
        .map(normalize_text)
    )

    mapping = mapping[
        mapping["stop_id"].ne("")
        & mapping[
            "canonical_station_id"
        ].ne("")
    ]

    return dict(
        zip(
            mapping["stop_id"],
            mapping[
                "canonical_station_id"
            ],
        )
    )


def load_trip_metadata(
    valid_route_ids: set[str],
) -> dict[str, tuple[str, str]]:
    if not TRIPS_FILE.exists():
        raise FileNotFoundError(
            f"trips.txt wurde nicht gefunden:\n{TRIPS_FILE}"
        )

    trips = pd.read_csv(
        TRIPS_FILE,
        dtype=str,
        usecols=[
            "trip_id",
            "route_id",
            "direction_id",
        ],
        low_memory=False,
    )

    trips["trip_id"] = (
        trips["trip_id"]
        .map(normalize_text)
    )

    trips["route_id"] = (
        trips["route_id"]
        .map(normalize_text)
    )

    trips["direction_id"] = (
        trips["direction_id"]
        .map(normalize_text)
    )

    trips = trips[
        trips["trip_id"].ne("")
        & trips["route_id"].isin(
            valid_route_ids
        )
    ]

    return {
        row.trip_id: (
            row.route_id,
            row.direction_id,
        )
        for row in trips.itertuples(
            index=False
        )
    }


def load_stop_times(
    stop_mapping: dict[str, str],
    valid_trip_ids: set[str],
) -> tuple[pd.DataFrame, int]:
    if not STOP_TIMES_FILE.exists():
        raise FileNotFoundError(
            "stop_times.txt wurde nicht gefunden:\n"
            f"{STOP_TIMES_FILE}"
        )

    stop_times = pd.read_csv(
        STOP_TIMES_FILE,
        dtype=str,
        usecols=[
            "trip_id",
            "arrival_time",
            "departure_time",
            "stop_id",
            "stop_sequence",
        ],
        low_memory=False,
    )

    original_row_count = len(
        stop_times
    )

    stop_times["trip_id"] = (
        stop_times["trip_id"]
        .map(normalize_text)
    )

    stop_times = stop_times[
        stop_times["trip_id"].isin(
            valid_trip_ids
        )
    ].copy()

    stop_times["station_id"] = (
        stop_times["stop_id"]
        .map(stop_mapping)
    )

    stop_times["stop_sequence_number"] = (
        pd.to_numeric(
            stop_times["stop_sequence"],
            errors="coerce",
        )
    )

    stop_times = stop_times[
        stop_times[
            "stop_sequence_number"
        ].notna()
    ].copy()

    print(
        "\nSortiere stop_times nach Fahrt "
        "und Haltestellenfolge ..."
    )

    stop_times.sort_values(
        by=[
            "trip_id",
            "stop_sequence_number",
        ],
        inplace=True,
        kind="mergesort",
    )

    return (
        stop_times,
        original_row_count,
    )


def collect_valid_edge_keys(
    travel_graph: dict[
        str,
        list[dict[str, Any]],
    ],
) -> set[
    tuple[str, str, str, str]
]:
    valid_edge_keys: set[
        tuple[str, str, str, str]
    ] = set()

    for (
        from_station_id,
        edges,
    ) in travel_graph.items():
        for edge in edges:
            valid_edge_keys.add(
                (
                    normalize_text(
                        from_station_id
                    ),
                    normalize_text(
                        edge.get("to")
                    ),
                    normalize_text(
                        edge.get("route_id")
                    ),
                    normalize_text(
                        edge.get(
                            "direction_id"
                        )
                    ),
                )
            )

    return valid_edge_keys


def create_empty_time_stat() -> dict[str, Any]:
    return {
        "duration_counts": Counter(),
        "sample_count": 0,
        "duration_sum": 0,
        "minimum": None,
        "maximum": None,
    }


def update_time_stat(
    time_stat: dict[str, Any],
    duration_seconds: int,
) -> None:
    # Auf fünf Sekunden runden. Dadurch bleibt der
    # Counter klein, ohne die Qualität merklich zu ändern.
    rounded_duration = int(
        round(
            duration_seconds / 5
        )
        * 5
    )

    rounded_duration = max(
        5,
        rounded_duration,
    )

    time_stat[
        "duration_counts"
    ][
        rounded_duration
    ] += 1

    time_stat[
        "sample_count"
    ] += 1

    time_stat[
        "duration_sum"
    ] += duration_seconds

    current_minimum = (
        time_stat["minimum"]
    )

    current_maximum = (
        time_stat["maximum"]
    )

    if (
        current_minimum is None
        or duration_seconds
        < current_minimum
    ):
        time_stat[
            "minimum"
        ] = duration_seconds

    if (
        current_maximum is None
        or duration_seconds
        > current_maximum
    ):
        time_stat[
            "maximum"
        ] = duration_seconds


def weighted_median(
    duration_counts: Counter[int],
) -> int:
    total_count = sum(
        duration_counts.values()
    )

    if total_count <= 0:
        raise ValueError(
            "Median kann ohne Werte "
            "nicht berechnet werden."
        )

    target_position = (
        total_count + 1
    ) // 2

    cumulative_count = 0

    for (
        duration,
        count,
    ) in sorted(
        duration_counts.items()
    ):
        cumulative_count += count

        if (
            cumulative_count
            >= target_position
        ):
            return int(duration)

    return int(
        max(duration_counts)
    )


def collect_ride_time_statistics(
    stop_times: pd.DataFrame,
    trip_metadata: dict[
        str,
        tuple[str, str],
    ],
    valid_edge_keys: set[
        tuple[str, str, str, str]
    ],
) -> tuple[
    dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ],
    dict[str, int],
]:
    edge_time_statistics: dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ] = {}

    statistics = {
        "processed_rows": 0,
        "processed_trips": 0,
        "unmapped_stop_rows": 0,
        "missing_time_rows": 0,
        "invalid_duration_samples": 0,
        "edge_not_in_graph_samples": 0,
        "accepted_time_samples": 0,
    }

    time_cache: dict[
        str,
        int | None,
    ] = {}

    current_trip_id: str | None = None
    current_route_id = ""
    current_direction_id = ""

    current_station_id: str | None = None
    current_arrival_seconds: int | None = None
    current_departure_seconds: int | None = None

    for row in stop_times.itertuples(
        index=False
    ):
        statistics[
            "processed_rows"
        ] += 1

        trip_id = normalize_text(
            row.trip_id
        )

        if (
            trip_id
            != current_trip_id
        ):
            current_trip_id = trip_id

            trip_info = (
                trip_metadata.get(
                    trip_id
                )
            )

            if trip_info is None:
                current_route_id = ""
                current_direction_id = ""
            else:
                (
                    current_route_id,
                    current_direction_id,
                ) = trip_info

                statistics[
                    "processed_trips"
                ] += 1

            current_station_id = None
            current_arrival_seconds = None
            current_departure_seconds = None

        if not current_route_id:
            continue

        station_id = normalize_text(
            row.station_id
        )

        if not station_id:
            statistics[
                "unmapped_stop_rows"
            ] += 1

            # Nicht über einen unbekannten Halt hinweg
            # eine künstliche Verbindung erzeugen.
            current_station_id = None
            current_arrival_seconds = None
            current_departure_seconds = None

            continue

        arrival_seconds = (
            parse_gtfs_time(
                row.arrival_time,
                time_cache,
            )
        )

        departure_seconds = (
            parse_gtfs_time(
                row.departure_time,
                time_cache,
            )
        )

        if arrival_seconds is None:
            arrival_seconds = (
                departure_seconds
            )

        if departure_seconds is None:
            departure_seconds = (
                arrival_seconds
            )

        if (
            arrival_seconds is None
            and departure_seconds is None
        ):
            statistics[
                "missing_time_rows"
            ] += 1

            current_station_id = None
            current_arrival_seconds = None
            current_departure_seconds = None

            continue

        if current_station_id is None:
            current_station_id = (
                station_id
            )

            current_arrival_seconds = (
                arrival_seconds
            )

            current_departure_seconds = (
                departure_seconds
            )

            continue

        # Mehrere Bahnsteig-/Stop-Zeilen derselben
        # logischen Station werden zusammengefasst.
        if (
            station_id
            == current_station_id
        ):
            if (
                current_arrival_seconds
                is None
            ):
                current_arrival_seconds = (
                    arrival_seconds
                )

            if (
                departure_seconds
                is not None
            ):
                current_departure_seconds = (
                    departure_seconds
                )

            continue

        if (
            current_departure_seconds
            is not None
            and arrival_seconds
            is not None
        ):
            duration_seconds = (
                arrival_seconds
                - current_departure_seconds
            )

            # Sicherheit für Fahrten über Mitternacht.
            while duration_seconds < 0:
                duration_seconds += 86400

            edge_key = (
                current_station_id,
                station_id,
                current_route_id,
                current_direction_id,
            )

            if (
                duration_seconds
                < MIN_VALID_RIDE_TIME_SECONDS
                or duration_seconds
                > MAX_VALID_RIDE_TIME_SECONDS
            ):
                statistics[
                    "invalid_duration_samples"
                ] += 1

            elif (
                edge_key
                not in valid_edge_keys
            ):
                statistics[
                    "edge_not_in_graph_samples"
                ] += 1

            else:
                if (
                    edge_key
                    not in edge_time_statistics
                ):
                    edge_time_statistics[
                        edge_key
                    ] = (
                        create_empty_time_stat()
                    )

                update_time_stat(
                    edge_time_statistics[
                        edge_key
                    ],
                    duration_seconds,
                )

                statistics[
                    "accepted_time_samples"
                ] += 1

        current_station_id = (
            station_id
        )

        current_arrival_seconds = (
            arrival_seconds
        )

        current_departure_seconds = (
            departure_seconds
        )

    return (
        edge_time_statistics,
        statistics,
    )


def get_default_ride_time(
    route_type: str,
) -> int:
    return DEFAULT_RIDE_TIMES_SECONDS.get(
        normalize_text(route_type),
        DEFAULT_RIDE_TIME_SECONDS,
    )


def build_weighted_graph(
    travel_graph: dict[
        str,
        list[dict[str, Any]],
    ],
    transfer_graph: dict[
        str,
        list[dict[str, Any]],
    ],
    edge_time_statistics: dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ],
    travel_stations: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, int],
]:
    weighted_graph: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    review_rows: list[
        dict[str, Any]
    ] = []

    statistics = {
        "ride_edges_with_gtfs_time": 0,
        "ride_edges_with_fallback_time": 0,
        "transfer_edges": 0,
    }

    for (
        from_station_id,
        edges,
    ) in travel_graph.items():
        for edge in edges:
            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            route_id = normalize_text(
                edge.get("route_id")
            )

            direction_id = (
                normalize_text(
                    edge.get(
                        "direction_id"
                    )
                )
            )

            route_type = (
                normalize_text(
                    edge.get(
                        "route_type"
                    )
                )
            )

            edge_key = (
                normalize_text(
                    from_station_id
                ),
                to_station_id,
                route_id,
                direction_id,
            )

            time_stat = (
                edge_time_statistics.get(
                    edge_key
                )
            )

            if (
                time_stat is not None
                and time_stat[
                    "sample_count"
                ] > 0
            ):
                travel_time_seconds = (
                    weighted_median(
                        time_stat[
                            "duration_counts"
                        ]
                    )
                )

                average_time_seconds = int(
                    round(
                        time_stat[
                            "duration_sum"
                        ]
                        / time_stat[
                            "sample_count"
                        ]
                    )
                )

                time_source = (
                    "gtfs_median"
                )

                sample_count = (
                    time_stat[
                        "sample_count"
                    ]
                )

                minimum_time = (
                    time_stat["minimum"]
                )

                maximum_time = (
                    time_stat["maximum"]
                )

                statistics[
                    "ride_edges_with_gtfs_time"
                ] += 1

            else:
                travel_time_seconds = (
                    get_default_ride_time(
                        route_type
                    )
                )

                average_time_seconds = (
                    travel_time_seconds
                )

                time_source = (
                    "route_type_fallback"
                )

                sample_count = 0
                minimum_time = None
                maximum_time = None

                statistics[
                    "ride_edges_with_fallback_time"
                ] += 1

            weighted_edge = {
                **edge,
                "edge_type": "ride",
                "travel_time_seconds": (
                    travel_time_seconds
                ),
                "time_source": (
                    time_source
                ),
                "time_sample_count": (
                    sample_count
                ),
                "average_time_seconds": (
                    average_time_seconds
                ),
                "minimum_time_seconds": (
                    minimum_time
                ),
                "maximum_time_seconds": (
                    maximum_time
                ),
            }

            weighted_graph[
                from_station_id
            ].append(
                weighted_edge
            )

            from_name = (
                travel_stations.get(
                    from_station_id,
                    {},
                ).get(
                    "name",
                    from_station_id,
                )
            )

            to_name = (
                travel_stations.get(
                    to_station_id,
                    {},
                ).get(
                    "name",
                    to_station_id,
                )
            )

            review_rows.append(
                {
                    "edge_type": "ride",
                    "from_station_id": (
                        from_station_id
                    ),
                    "from_station_name": (
                        from_name
                    ),
                    "to_station_id": (
                        to_station_id
                    ),
                    "to_station_name": (
                        to_name
                    ),
                    "route_id": (
                        route_id
                    ),
                    "route_short_name": (
                        edge.get(
                            "route_short_name",
                            "",
                        )
                    ),
                    "direction_id": (
                        direction_id
                    ),
                    "route_type": (
                        route_type
                    ),
                    "travel_time_seconds": (
                        travel_time_seconds
                    ),
                    "travel_time_minutes": round(
                        travel_time_seconds
                        / 60,
                        2,
                    ),
                    "time_source": (
                        time_source
                    ),
                    "time_sample_count": (
                        sample_count
                    ),
                    "average_time_seconds": (
                        average_time_seconds
                    ),
                    "minimum_time_seconds": (
                        minimum_time
                    ),
                    "maximum_time_seconds": (
                        maximum_time
                    ),
                }
            )

    for (
        from_station_id,
        edges,
    ) in transfer_graph.items():
        for edge in edges:
            travel_time_seconds = int(
                edge.get(
                    "routing_time_seconds",
                    180,
                )
                or 180
            )

            weighted_edge = {
                **edge,
                "edge_type": "transfer",
                "travel_time_seconds": (
                    travel_time_seconds
                ),
            }

            weighted_graph[
                from_station_id
            ].append(
                weighted_edge
            )

            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            from_name = (
                travel_stations.get(
                    from_station_id,
                    {},
                ).get(
                    "name",
                    from_station_id,
                )
            )

            to_name = (
                travel_stations.get(
                    to_station_id,
                    {},
                ).get(
                    "name",
                    to_station_id,
                )
            )

            review_rows.append(
                {
                    "edge_type": "transfer",
                    "from_station_id": (
                        from_station_id
                    ),
                    "from_station_name": (
                        from_name
                    ),
                    "to_station_id": (
                        to_station_id
                    ),
                    "to_station_name": (
                        to_name
                    ),
                    "route_id": "",
                    "route_short_name": "",
                    "direction_id": "",
                    "route_type": "",
                    "travel_time_seconds": (
                        travel_time_seconds
                    ),
                    "travel_time_minutes": round(
                        travel_time_seconds
                        / 60,
                        2,
                    ),
                    "time_source": (
                        edge.get(
                            "time_source",
                            "transfer",
                        )
                    ),
                    "time_sample_count": (
                        edge.get(
                            "source_count",
                            0,
                        )
                    ),
                    "average_time_seconds": "",
                    "minimum_time_seconds": "",
                    "maximum_time_seconds": "",
                }
            )

            statistics[
                "transfer_edges"
            ] += 1

    for station_id in weighted_graph:
        weighted_graph[
            station_id
        ].sort(
            key=lambda edge: (
                0
                if edge.get(
                    "edge_type"
                ) == "ride"
                else 1,
                normalize_text(
                    edge.get(
                        "route_short_name"
                    )
                ),
                normalize_text(
                    edge.get("to")
                ),
            )
        )

    return (
        dict(weighted_graph),
        review_rows,
        statistics,
    )


def print_example_edges(
    weighted_graph: dict[
        str,
        list[dict[str, Any]],
    ],
    travel_stations: dict[str, Any],
) -> None:
    example_names = [
        "Esslingen (N)",
        "Hauptbahnhof (tief)",
        "Marienplatz",
    ]

    print(
        "\nBeispielhafte gewichtete Kanten:"
    )

    for station_name in example_names:
        matching_ids = [
            station_id
            for (
                station_id,
                station,
            ) in travel_stations.items()
            if normalize_text(
                station.get("name")
            ).casefold()
            == station_name.casefold()
        ]

        print(
            f"\n{station_name}:"
        )

        if not matching_ids:
            print(
                "- Station nicht gefunden"
            )
            continue

        station_id = matching_ids[0]

        edges = weighted_graph.get(
            station_id,
            [],
        )

        if not edges:
            print(
                "- keine ausgehenden Kanten"
            )
            continue

        for edge in edges[:15]:
            target_name = (
                travel_stations.get(
                    edge.get("to"),
                    {},
                ).get(
                    "name",
                    edge.get("to"),
                )
            )

            minutes = (
                edge[
                    "travel_time_seconds"
                ]
                / 60
            )

            if (
                edge.get("edge_type")
                == "transfer"
            ):
                print(
                    "- Fußweg "
                    f"→ {target_name} "
                    f"| {minutes:.1f} Minuten "
                    f"| {edge.get('time_source', '')}"
                )
            else:
                print(
                    "- "
                    f"{edge.get('route_short_name', '')} "
                    f"→ {target_name} "
                    f"| {minutes:.1f} Minuten "
                    f"| {edge.get('time_source', '')} "
                    f"| Samples: "
                    f"{edge.get('time_sample_count', 0)}"
                )


def main() -> None:
    travel_stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    travel_graph = load_json(
        TRAVEL_GRAPH_FILE
    )

    transfer_graph = load_json(
        TRAVEL_TRANSFERS_FILE
    )

    valid_edge_keys = (
        collect_valid_edge_keys(
            travel_graph
        )
    )

    valid_route_ids = {
        edge_key[2]
        for edge_key
        in valid_edge_keys
    }

    print("=" * 72)
    print("GEWICHTETEN TRAVEL-GRAPH ERSTELLEN")
    print("=" * 72)

    print(
        f"Fahrkanten im Graph: "
        f"{len(valid_edge_keys):,}"
    )

    print(
        f"Relevante Routen: "
        f"{len(valid_route_ids):,}"
    )

    stop_mapping = (
        load_stop_mapping()
    )

    trip_metadata = (
        load_trip_metadata(
            valid_route_ids
        )
    )

    print(
        f"Relevante Trips: "
        f"{len(trip_metadata):,}"
    )

    (
        stop_times,
        original_stop_time_rows,
    ) = load_stop_times(
        stop_mapping,
        set(
            trip_metadata.keys()
        ),
    )

    print(
        f"GTFS-stop_times gesamt: "
        f"{original_stop_time_rows:,}"
    )

    print(
        f"Relevante stop_times: "
        f"{len(stop_times):,}"
    )

    (
        edge_time_statistics,
        collection_statistics,
    ) = collect_ride_time_statistics(
        stop_times,
        trip_metadata,
        valid_edge_keys,
    )

    # Große Tabelle vor dem JSON-Bau freigeben.
    del stop_times

    (
        weighted_graph,
        review_rows,
        graph_statistics,
    ) = build_weighted_graph(
        travel_graph,
        transfer_graph,
        edge_time_statistics,
        travel_stations,
    )

    save_json(
        OUTPUT_WEIGHTED_GRAPH_JSON,
        weighted_graph,
    )

    pd.DataFrame(
        review_rows
    ).to_csv(
        OUTPUT_REVIEW_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\n" + "=" * 72
    )

    print(
        "GEWICHTETER GRAPH ERFOLGREICH ERSTELLT"
    )

    print("=" * 72)

    print(
        "Verarbeitete Trips:             "
        f"{collection_statistics['processed_trips']:,}"
    )

    print(
        "Verarbeitete stop_times:        "
        f"{collection_statistics['processed_rows']:,}"
    )

    print(
        "Akzeptierte Fahrzeit-Samples:   "
        f"{collection_statistics['accepted_time_samples']:,}"
    )

    print(
        "Ungültige Fahrzeiten:           "
        f"{collection_statistics['invalid_duration_samples']:,}"
    )

    print(
        "Nicht im Graph gefundene Werte: "
        f"{collection_statistics['edge_not_in_graph_samples']:,}"
    )

    print(
        "Fahrkanten mit GTFS-Zeit:       "
        f"{graph_statistics['ride_edges_with_gtfs_time']:,}"
    )

    print(
        "Fahrkanten mit Ersatzwert:      "
        f"{graph_statistics['ride_edges_with_fallback_time']:,}"
    )

    print(
        "Transferkanten:                 "
        f"{graph_statistics['transfer_edges']:,}"
    )

    print(
        "Graph-Knoten insgesamt:         "
        f"{len(weighted_graph):,}"
    )

    print(
        "\nGewichteter Graph:\n"
        f"{OUTPUT_WEIGHTED_GRAPH_JSON}"
    )

    print(
        "\nKontroll-CSV:\n"
        f"{OUTPUT_REVIEW_CSV}"
    )

    print_example_edges(
        weighted_graph,
        travel_stations,
    )


if __name__ == "__main__":
    main()