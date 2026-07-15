from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRAVEL_STATIONS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

TRAVEL_ROUTES_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_routes.json"
)

ROUTE_PATTERNS_FILE = (
    PROJECT_ROOT
    / "output"
    / "route_patterns.json"
)

WEIGHTED_GRAPH_FILE = (
    PROJECT_ROOT
    / "output"
    / "weighted_travel_graph.json"
)

OUTPUT_MOVE_INDEX_JSON = (
    PROJECT_ROOT
    / "output"
    / "travel_move_index.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "travel_move_index_review.csv"
)

DEFAULT_RIDE_TIME_SECONDS = 120


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def parse_positive_int(
    value: Any,
    default: int,
) -> int:
    try:
        parsed_value = int(
            round(
                float(value)
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    if parsed_value <= 0:
        return default

    return parsed_value


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


def save_compact_json(
    path: Path,
    data: Any,
) -> None:
    """
    Der Move-Index kann relativ groß werden.

    Deshalb wird das JSON kompakt ohne Einrückungen
    gespeichert. Für die manuelle Kontrolle gibt es
    zusätzlich eine lesbare CSV-Datei.
    """

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
            separators=(
                ",",
                ":",
            ),
        )


def natural_sort_key(
    value: Any,
) -> tuple[Any, ...]:
    """
    Sortiert beispielsweise:

    U1, U2, U12

    statt:

    U1, U12, U2
    """

    text = normalize_text(
        value
    ).casefold()

    parts = re.split(
        r"(\d+)",
        text,
    )

    key_parts: list[
        tuple[int, Any]
    ] = []

    for part in parts:
        if not part:
            continue

        if part.isdigit():
            key_parts.append(
                (
                    0,
                    int(part),
                )
            )
        else:
            key_parts.append(
                (
                    1,
                    part,
                )
            )

    return tuple(
        key_parts
    )


def make_service_key(
    route_id: str,
    direction_id: str,
) -> str:
    return (
        f"{route_id}"
        f"::{direction_id}"
    )


def get_station_name(
    stations: dict[
        str,
        dict[str, Any],
    ],
    station_id: str,
) -> str:
    return (
        normalize_text(
            stations.get(
                station_id,
                {},
            ).get(
                "name",
                station_id,
            )
        )
        or station_id
    )


def build_ride_edge_lookup(
    weighted_graph: dict[
        str,
        list[dict[str, Any]],
    ],
) -> tuple[
    dict[
        tuple[
            str,
            str,
            str,
            str,
        ],
        int,
    ],
    dict[str, int],
]:
    """
    Erzeugt einen schnellen Lookup:

    Startstation
    + Zielstation
    + route_id
    + direction_id

    → Fahrzeit in Sekunden
    """

    edge_lookup: dict[
        tuple[
            str,
            str,
            str,
            str,
        ],
        int,
    ] = {}

    statistics = {
        "ride_edges": 0,
        "transfer_edges_ignored": 0,
        "duplicate_ride_edges": 0,
    }

    for (
        from_station_id,
        edges,
    ) in weighted_graph.items():
        normalized_from_id = (
            normalize_text(
                from_station_id
            )
        )

        for edge in edges:
            edge_type = (
                normalize_text(
                    edge.get(
                        "edge_type"
                    )
                )
            )

            if edge_type != "ride":
                statistics[
                    "transfer_edges_ignored"
                ] += 1

                continue

            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            route_id = (
                normalize_text(
                    edge.get(
                        "route_id"
                    )
                )
            )

            direction_id = (
                normalize_text(
                    edge.get(
                        "direction_id"
                    )
                )
            )

            if (
                not normalized_from_id
                or not to_station_id
                or not route_id
            ):
                continue

            travel_time_seconds = (
                parse_positive_int(
                    edge.get(
                        "travel_time_seconds"
                    ),
                    DEFAULT_RIDE_TIME_SECONDS,
                )
            )

            edge_key = (
                normalized_from_id,
                to_station_id,
                route_id,
                direction_id,
            )

            if edge_key in edge_lookup:
                statistics[
                    "duplicate_ride_edges"
                ] += 1

                edge_lookup[
                    edge_key
                ] = min(
                    edge_lookup[
                        edge_key
                    ],
                    travel_time_seconds,
                )
            else:
                edge_lookup[
                    edge_key
                ] = (
                    travel_time_seconds
                )

                statistics[
                    "ride_edges"
                ] += 1

    return (
        edge_lookup,
        statistics,
    )


def create_service_entry(
    route_id: str,
    direction_id: str,
    route: dict[str, Any],
) -> dict[str, Any]:
    return {
        "service_key": make_service_key(
            route_id,
            direction_id,
        ),
        "route_id": route_id,
        "route_short_name": (
            normalize_text(
                route.get(
                    "short_name"
                )
            )
        ),
        "route_long_name": (
            normalize_text(
                route.get(
                    "long_name"
                )
            )
        ),
        "route_type": (
            normalize_text(
                route.get(
                    "route_type"
                )
            )
        ),
        "direction_id": (
            direction_id
        ),
        "headsigns": set(),
        "pattern_trip_counts": {},
        "destinations": {},
    }


def create_destination_entry(
    destination_station_id: str,
) -> dict[str, Any]:
    return {
        "station_id": (
            destination_station_id
        ),
        "headsigns": set(),
        "pattern_trip_counts": {},
        "minimum_time_seconds": None,
        "maximum_time_seconds": None,
        "minimum_stop_count": None,
        "maximum_stop_count": None,
        "representative_score": None,
        "representative_pattern_id": "",
        "representative_from_index": 0,
        "representative_to_index": 0,
        "representative_stop_count": 0,
        "representative_time_seconds": 0,
    }


def update_destination_entry(
    destination: dict[str, Any],
    pattern_id: str,
    headsign: str,
    trip_count: int,
    from_index: int,
    to_index: int,
    stop_count: int,
    travel_time_seconds: int,
) -> None:
    if headsign:
        destination[
            "headsigns"
        ].add(
            headsign
        )

    previous_trip_count = (
        destination[
            "pattern_trip_counts"
        ].get(
            pattern_id
        )
    )

    if previous_trip_count is None:
        destination[
            "pattern_trip_counts"
        ][
            pattern_id
        ] = trip_count
    else:
        destination[
            "pattern_trip_counts"
        ][
            pattern_id
        ] = max(
            previous_trip_count,
            trip_count,
        )

    current_minimum_time = (
        destination[
            "minimum_time_seconds"
        ]
    )

    current_maximum_time = (
        destination[
            "maximum_time_seconds"
        ]
    )

    if (
        current_minimum_time is None
        or travel_time_seconds
        < current_minimum_time
    ):
        destination[
            "minimum_time_seconds"
        ] = travel_time_seconds

    if (
        current_maximum_time is None
        or travel_time_seconds
        > current_maximum_time
    ):
        destination[
            "maximum_time_seconds"
        ] = travel_time_seconds

    current_minimum_stops = (
        destination[
            "minimum_stop_count"
        ]
    )

    current_maximum_stops = (
        destination[
            "maximum_stop_count"
        ]
    )

    if (
        current_minimum_stops is None
        or stop_count
        < current_minimum_stops
    ):
        destination[
            "minimum_stop_count"
        ] = stop_count

    if (
        current_maximum_stops is None
        or stop_count
        > current_maximum_stops
    ):
        destination[
            "maximum_stop_count"
        ] = stop_count

    # Repräsentative Fahrt:
    #
    # 1. Pattern mit höherer Fahrtenzahl
    # 2. danach weniger Haltestellen
    # 3. danach geringere Fahrzeit
    #
    # Dadurch wird normalerweise nicht eine seltene
    # Sonderfahrt als Standardverbindung angezeigt.
    representative_score = (
        trip_count,
        -stop_count,
        -travel_time_seconds,
        pattern_id,
    )

    current_score = (
        destination[
            "representative_score"
        ]
    )

    if (
        current_score is None
        or representative_score
        > current_score
    ):
        destination[
            "representative_score"
        ] = (
            representative_score
        )

        destination[
            "representative_pattern_id"
        ] = pattern_id

        destination[
            "representative_from_index"
        ] = from_index

        destination[
            "representative_to_index"
        ] = to_index

        destination[
            "representative_stop_count"
        ] = stop_count

        destination[
            "representative_time_seconds"
        ] = travel_time_seconds


def build_move_index(
    route_patterns: dict[
        str,
        dict[str, Any],
    ],
    travel_routes: dict[
        str,
        dict[str, Any],
    ],
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    ride_edge_lookup: dict[
        tuple[
            str,
            str,
            str,
            str,
        ],
        int,
    ],
) -> tuple[
    dict[str, Any],
    dict[str, int],
]:
    """
    Erstellt alle legalen Fahrtzüge.

    Aus einem Pattern:

    A → B → C → D

    entstehen ab A beispielsweise:

    A → B
    A → C
    A → D

    Ab B entstehen:

    B → C
    B → D
    """

    station_service_groups: dict[
        str,
        dict[
            tuple[str, str],
            dict[str, Any],
        ],
    ] = {}

    statistics = {
        "patterns_total": len(
            route_patterns
        ),
        "patterns_processed": 0,
        "patterns_skipped_missing_route": 0,
        "patterns_skipped_too_short": 0,
        "patterns_skipped_unknown_station": 0,
        "patterns_skipped_missing_edge": 0,
        "candidate_moves_processed": 0,
    }

    for (
        pattern_id,
        pattern,
    ) in route_patterns.items():
        route_id = normalize_text(
            pattern.get(
                "route_id"
            )
        )

        direction_id = normalize_text(
            pattern.get(
                "direction_id"
            )
        )

        route = travel_routes.get(
            route_id
        )

        if route is None:
            statistics[
                "patterns_skipped_missing_route"
            ] += 1

            continue

        station_ids = [
            normalize_text(
                station_id
            )
            for station_id
            in pattern.get(
                "station_ids",
                [],
            )
            if normalize_text(
                station_id
            )
        ]

        if len(station_ids) < 2:
            statistics[
                "patterns_skipped_too_short"
            ] += 1

            continue

        unknown_station_ids = [
            station_id
            for station_id
            in station_ids
            if station_id
            not in travel_stations
        ]

        if unknown_station_ids:
            statistics[
                "patterns_skipped_unknown_station"
            ] += 1

            continue

        edge_times: list[int] = []
        missing_edge = False

        for edge_index in range(
            len(station_ids) - 1
        ):
            from_station_id = (
                station_ids[
                    edge_index
                ]
            )

            to_station_id = (
                station_ids[
                    edge_index + 1
                ]
            )

            edge_key = (
                from_station_id,
                to_station_id,
                route_id,
                direction_id,
            )

            travel_time_seconds = (
                ride_edge_lookup.get(
                    edge_key
                )
            )

            if travel_time_seconds is None:
                missing_edge = True
                break

            edge_times.append(
                travel_time_seconds
            )

        if missing_edge:
            statistics[
                "patterns_skipped_missing_edge"
            ] += 1

            continue

        prefix_times = [0]

        for edge_time in edge_times:
            prefix_times.append(
                prefix_times[-1]
                + edge_time
            )

        headsign = normalize_text(
            pattern.get(
                "headsign"
            )
        )

        trip_count = (
            parse_positive_int(
                pattern.get(
                    "trip_count"
                ),
                1,
            )
        )

        statistics[
            "patterns_processed"
        ] += 1

        for from_index in range(
            len(station_ids) - 1
        ):
            from_station_id = (
                station_ids[
                    from_index
                ]
            )

            station_services = (
                station_service_groups
                .setdefault(
                    from_station_id,
                    {},
                )
            )

            service_key = (
                route_id,
                direction_id,
            )

            service = (
                station_services.get(
                    service_key
                )
            )

            if service is None:
                service = (
                    create_service_entry(
                        route_id,
                        direction_id,
                        route,
                    )
                )

                station_services[
                    service_key
                ] = service

            if headsign:
                service[
                    "headsigns"
                ].add(
                    headsign
                )

            previous_pattern_count = (
                service[
                    "pattern_trip_counts"
                ].get(
                    pattern_id
                )
            )

            if previous_pattern_count is None:
                service[
                    "pattern_trip_counts"
                ][
                    pattern_id
                ] = trip_count
            else:
                service[
                    "pattern_trip_counts"
                ][
                    pattern_id
                ] = max(
                    previous_pattern_count,
                    trip_count,
                )

            for to_index in range(
                from_index + 1,
                len(station_ids),
            ):
                to_station_id = (
                    station_ids[
                        to_index
                    ]
                )

                # Bei Ring- oder Schleifenlinien kann dieselbe
                # logische Station später erneut auftauchen.
                # Ein Zug von einer Station zu sich selbst ist
                # für das Spiel nicht sinnvoll.
                if (
                    to_station_id
                    == from_station_id
                ):
                    continue

                stop_count = (
                    to_index
                    - from_index
                )

                travel_time_seconds = (
                    prefix_times[
                        to_index
                    ]
                    - prefix_times[
                        from_index
                    ]
                )

                destinations = (
                    service[
                        "destinations"
                    ]
                )

                destination = (
                    destinations.get(
                        to_station_id
                    )
                )

                if destination is None:
                    destination = (
                        create_destination_entry(
                            to_station_id
                        )
                    )

                    destinations[
                        to_station_id
                    ] = destination

                update_destination_entry(
                    destination=destination,
                    pattern_id=pattern_id,
                    headsign=headsign,
                    trip_count=trip_count,
                    from_index=from_index,
                    to_index=to_index,
                    stop_count=stop_count,
                    travel_time_seconds=(
                        travel_time_seconds
                    ),
                )

                statistics[
                    "candidate_moves_processed"
                ] += 1

    station_moves: dict[
        str,
        dict[str, Any],
    ] = {}

    service_option_count = 0
    legal_move_count = 0

    for (
        station_id,
        service_groups,
    ) in station_service_groups.items():
        finalized_services: list[
            dict[str, Any]
        ] = []

        sorted_services = sorted(
            service_groups.values(),
            key=lambda service: (
                natural_sort_key(
                    service[
                        "route_short_name"
                    ]
                ),
                service[
                    "route_type"
                ],
                service[
                    "route_id"
                ],
                service[
                    "direction_id"
                ],
            ),
        )

        for service in sorted_services:
            finalized_destinations: list[
                dict[str, Any]
            ] = []

            destination_values = (
                service[
                    "destinations"
                ].values()
            )

            sorted_destinations = sorted(
                destination_values,
                key=lambda destination: (
                    destination[
                        "representative_stop_count"
                    ],
                    destination[
                        "representative_time_seconds"
                    ],
                    get_station_name(
                        travel_stations,
                        destination[
                            "station_id"
                        ],
                    ).casefold(),
                    destination[
                        "station_id"
                    ],
                ),
            )

            for destination in (
                sorted_destinations
            ):
                pattern_trip_counts = (
                    destination[
                        "pattern_trip_counts"
                    ]
                )

                finalized_destinations.append(
                    {
                        "station_id": (
                            destination[
                                "station_id"
                            ]
                        ),
                        "headsigns": sorted(
                            destination[
                                "headsigns"
                            ]
                        ),
                        "stop_count": (
                            destination[
                                "representative_stop_count"
                            ]
                        ),
                        "travel_time_seconds": (
                            destination[
                                "representative_time_seconds"
                            ]
                        ),
                        "minimum_stop_count": (
                            destination[
                                "minimum_stop_count"
                            ]
                        ),
                        "maximum_stop_count": (
                            destination[
                                "maximum_stop_count"
                            ]
                        ),
                        "minimum_time_seconds": (
                            destination[
                                "minimum_time_seconds"
                            ]
                        ),
                        "maximum_time_seconds": (
                            destination[
                                "maximum_time_seconds"
                            ]
                        ),
                        "support_trip_count": sum(
                            pattern_trip_counts.values()
                        ),
                        "pattern_count": len(
                            pattern_trip_counts
                        ),
                        "representative_pattern_id": (
                            destination[
                                "representative_pattern_id"
                            ]
                        ),
                        "representative_from_index": (
                            destination[
                                "representative_from_index"
                            ]
                        ),
                        "representative_to_index": (
                            destination[
                                "representative_to_index"
                            ]
                        ),
                    }
                )

            service_pattern_counts = (
                service[
                    "pattern_trip_counts"
                ]
            )

            finalized_services.append(
                {
                    "service_key": (
                        service[
                            "service_key"
                        ]
                    ),
                    "route_id": (
                        service[
                            "route_id"
                        ]
                    ),
                    "route_short_name": (
                        service[
                            "route_short_name"
                        ]
                    ),
                    "route_long_name": (
                        service[
                            "route_long_name"
                        ]
                    ),
                    "route_type": (
                        service[
                            "route_type"
                        ]
                    ),
                    "direction_id": (
                        service[
                            "direction_id"
                        ]
                    ),
                    "headsigns": sorted(
                        service[
                            "headsigns"
                        ]
                    ),
                    "pattern_count": len(
                        service_pattern_counts
                    ),
                    "trip_count": sum(
                        service_pattern_counts.values()
                    ),
                    "destination_count": len(
                        finalized_destinations
                    ),
                    "destinations": (
                        finalized_destinations
                    ),
                }
            )

            service_option_count += 1
            legal_move_count += len(
                finalized_destinations
            )

        station_moves[
            station_id
        ] = {
            "station_name": (
                get_station_name(
                    travel_stations,
                    station_id,
                )
            ),
            "service_count": len(
                finalized_services
            ),
            "move_count": sum(
                service[
                    "destination_count"
                ]
                for service
                in finalized_services
            ),
            "services": (
                finalized_services
            ),
        }

    statistics[
        "stations_with_moves"
    ] = len(
        station_moves
    )

    statistics[
        "service_option_count"
    ] = service_option_count

    statistics[
        "legal_move_count"
    ] = legal_move_count

    move_index = {
        "metadata": {
            "version": 1,
            "source_pattern_count": len(
                route_patterns
            ),
            "station_count": len(
                travel_stations
            ),
            "stations_with_moves": len(
                station_moves
            ),
            "service_option_count": (
                service_option_count
            ),
            "legal_move_count": (
                legal_move_count
            ),
        },
        "station_moves": (
            station_moves
        ),
    }

    return (
        move_index,
        statistics,
    )


def write_review_csv(
    path: Path,
    move_index: dict[str, Any],
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "from_station_id",
        "from_station_name",
        "service_key",
        "route_id",
        "route_short_name",
        "route_long_name",
        "route_type",
        "direction_id",
        "service_headsigns",
        "to_station_id",
        "to_station_name",
        "destination_headsigns",
        "stop_count",
        "travel_time_seconds",
        "travel_time_minutes",
        "minimum_stop_count",
        "maximum_stop_count",
        "minimum_time_seconds",
        "maximum_time_seconds",
        "support_trip_count",
        "pattern_count",
        "representative_pattern_id",
        "representative_from_index",
        "representative_to_index",
    ]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        station_moves = (
            move_index[
                "station_moves"
            ]
        )

        for (
            from_station_id,
            station_entry,
        ) in station_moves.items():
            from_station_name = (
                station_entry[
                    "station_name"
                ]
            )

            for service in (
                station_entry[
                    "services"
                ]
            ):
                for destination in (
                    service[
                        "destinations"
                    ]
                ):
                    to_station_id = (
                        destination[
                            "station_id"
                        ]
                    )

                    writer.writerow(
                        {
                            "from_station_id": (
                                from_station_id
                            ),
                            "from_station_name": (
                                from_station_name
                            ),
                            "service_key": (
                                service[
                                    "service_key"
                                ]
                            ),
                            "route_id": (
                                service[
                                    "route_id"
                                ]
                            ),
                            "route_short_name": (
                                service[
                                    "route_short_name"
                                ]
                            ),
                            "route_long_name": (
                                service[
                                    "route_long_name"
                                ]
                            ),
                            "route_type": (
                                service[
                                    "route_type"
                                ]
                            ),
                            "direction_id": (
                                service[
                                    "direction_id"
                                ]
                            ),
                            "service_headsigns": (
                                " | ".join(
                                    service[
                                        "headsigns"
                                    ]
                                )
                            ),
                            "to_station_id": (
                                to_station_id
                            ),
                            "to_station_name": (
                                get_station_name(
                                    travel_stations,
                                    to_station_id,
                                )
                            ),
                            "destination_headsigns": (
                                " | ".join(
                                    destination[
                                        "headsigns"
                                    ]
                                )
                            ),
                            "stop_count": (
                                destination[
                                    "stop_count"
                                ]
                            ),
                            "travel_time_seconds": (
                                destination[
                                    "travel_time_seconds"
                                ]
                            ),
                            "travel_time_minutes": round(
                                destination[
                                    "travel_time_seconds"
                                ]
                                / 60,
                                2,
                            ),
                            "minimum_stop_count": (
                                destination[
                                    "minimum_stop_count"
                                ]
                            ),
                            "maximum_stop_count": (
                                destination[
                                    "maximum_stop_count"
                                ]
                            ),
                            "minimum_time_seconds": (
                                destination[
                                    "minimum_time_seconds"
                                ]
                            ),
                            "maximum_time_seconds": (
                                destination[
                                    "maximum_time_seconds"
                                ]
                            ),
                            "support_trip_count": (
                                destination[
                                    "support_trip_count"
                                ]
                            ),
                            "pattern_count": (
                                destination[
                                    "pattern_count"
                                ]
                            ),
                            "representative_pattern_id": (
                                destination[
                                    "representative_pattern_id"
                                ]
                            ),
                            "representative_from_index": (
                                destination[
                                    "representative_from_index"
                                ]
                            ),
                            "representative_to_index": (
                                destination[
                                    "representative_to_index"
                                ]
                            ),
                        }
                    )


def print_examples(
    move_index: dict[str, Any],
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    example_station_names = [
        "Esslingen (N)",
        "Hauptbahnhof (tief)",
        "Marienplatz",
        "Sonnenberg",
    ]

    station_moves = (
        move_index[
            "station_moves"
        ]
    )

    print(
        "\nBeispielhafte Spielzüge:"
    )

    for station_name in (
        example_station_names
    ):
        matching_station_ids = [
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

        if not matching_station_ids:
            print(
                "- Station nicht gefunden"
            )
            continue

        station_id = (
            matching_station_ids[0]
        )

        station_entry = (
            station_moves.get(
                station_id
            )
        )

        if station_entry is None:
            print(
                "- keine legalen Spielzüge"
            )
            continue

        print(
            "- Linien-/Richtungsoptionen: "
            f"{station_entry['service_count']}"
        )

        print(
            "- Mögliche Fahrtziele: "
            f"{station_entry['move_count']}"
        )

        for service in (
            station_entry[
                "services"
            ][:8]
        ):
            line_name = (
                service[
                    "route_short_name"
                ]
                or service[
                    "route_id"
                ]
            )

            direction_text = (
                ", ".join(
                    service[
                        "headsigns"
                    ][:2]
                )
                or "ohne Zielangabe"
            )

            destination_examples: list[
                str
            ] = []

            for destination in (
                service[
                    "destinations"
                ][:4]
            ):
                destination_name = (
                    get_station_name(
                        travel_stations,
                        destination[
                            "station_id"
                        ],
                    )
                )

                minutes = (
                    destination[
                        "travel_time_seconds"
                    ]
                    / 60
                )

                destination_examples.append(
                    f"{destination_name} "
                    f"({minutes:.1f} Min.)"
                )

            print(
                f"- {line_name} "
                f"| Richtung: {direction_text}"
            )

            print(
                "  Ausstiege: "
                + ", ".join(
                    destination_examples
                )
            )


def main() -> None:
    travel_stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    travel_routes = load_json(
        TRAVEL_ROUTES_FILE
    )

    route_patterns = load_json(
        ROUTE_PATTERNS_FILE
    )

    weighted_graph = load_json(
        WEIGHTED_GRAPH_FILE
    )

    if not isinstance(
        travel_stations,
        dict,
    ):
        raise ValueError(
            "travel_stations.json ist ungültig."
        )

    if not isinstance(
        travel_routes,
        dict,
    ):
        raise ValueError(
            "travel_routes.json ist ungültig."
        )

    if not isinstance(
        route_patterns,
        dict,
    ):
        raise ValueError(
            "route_patterns.json ist ungültig."
        )

    if not isinstance(
        weighted_graph,
        dict,
    ):
        raise ValueError(
            "weighted_travel_graph.json ist ungültig."
        )

    print("=" * 72)
    print("TRAVEL-MOVE-INDEX ERSTELLEN")
    print("=" * 72)

    print(
        f"Stationen:       "
        f"{len(travel_stations):,}"
    )

    print(
        f"Routen:          "
        f"{len(travel_routes):,}"
    )

    print(
        f"Route-Patterns:  "
        f"{len(route_patterns):,}"
    )

    (
        ride_edge_lookup,
        edge_statistics,
    ) = build_ride_edge_lookup(
        weighted_graph
    )

    print(
        f"Gewichtete Fahrkanten: "
        f"{len(ride_edge_lookup):,}"
    )

    (
        move_index,
        statistics,
    ) = build_move_index(
        route_patterns=route_patterns,
        travel_routes=travel_routes,
        travel_stations=travel_stations,
        ride_edge_lookup=ride_edge_lookup,
    )

    save_compact_json(
        OUTPUT_MOVE_INDEX_JSON,
        move_index,
    )

    write_review_csv(
        OUTPUT_REVIEW_CSV,
        move_index,
        travel_stations,
    )

    print(
        "\n" + "=" * 72
    )

    print(
        "TRAVEL-MOVE-INDEX ERFOLGREICH ERSTELLT"
    )

    print("=" * 72)

    print(
        "Verarbeitete Patterns:          "
        f"{statistics['patterns_processed']:,}"
    )

    print(
        "Patterns ohne Route:            "
        f"{statistics['patterns_skipped_missing_route']:,}"
    )

    print(
        "Zu kurze Patterns:              "
        f"{statistics['patterns_skipped_too_short']:,}"
    )

    print(
        "Patterns mit unbekannter Station:"
        f" {statistics['patterns_skipped_unknown_station']:,}"
    )

    print(
        "Patterns ohne gewichtete Kante: "
        f"{statistics['patterns_skipped_missing_edge']:,}"
    )

    print(
        "Verarbeitete Zugkandidaten:     "
        f"{statistics['candidate_moves_processed']:,}"
    )

    print(
        "Stationen mit Spielzügen:       "
        f"{statistics['stations_with_moves']:,}"
    )

    print(
        "Linien-/Richtungsoptionen:      "
        f"{statistics['service_option_count']:,}"
    )

    print(
        "Eindeutige legale Spielzüge:    "
        f"{statistics['legal_move_count']:,}"
    )

    print(
        "Ignorierte Transferkanten:      "
        f"{edge_statistics['transfer_edges_ignored']:,}"
    )

    print(
        "\nMove-Index:\n"
        f"{OUTPUT_MOVE_INDEX_JSON}"
    )

    print(
        "\nKontroll-CSV:\n"
        f"{OUTPUT_REVIEW_CSV}"
    )

    print_examples(
        move_index,
        travel_stations,
    )


if __name__ == "__main__":
    main()