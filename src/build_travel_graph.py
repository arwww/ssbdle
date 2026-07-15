from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRAVEL_STATIONS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

ROUTE_PATTERNS_FILE = (
    PROJECT_ROOT
    / "output"
    / "route_patterns.json"
)

TRAVEL_ROUTES_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_routes.json"
)

OUTPUT_GRAPH_JSON = (
    PROJECT_ROOT
    / "output"
    / "travel_graph.json"
)

OUTPUT_STATION_ROUTES_JSON = (
    PROJECT_ROOT
    / "output"
    / "station_routes.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "travel_graph_review.csv"
)


def normalize_text(value: Any) -> str:
    if value is None:
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


def validate_input_data(
    travel_stations: dict[str, Any],
    route_patterns: dict[str, Any],
    travel_routes: dict[str, Any],
) -> None:
    if not isinstance(
        travel_stations,
        dict,
    ):
        raise ValueError(
            "travel_stations.json muss "
            "ein JSON-Objekt enthalten."
        )

    if not isinstance(
        route_patterns,
        dict,
    ):
        raise ValueError(
            "route_patterns.json muss "
            "ein JSON-Objekt enthalten."
        )

    if not isinstance(
        travel_routes,
        dict,
    ):
        raise ValueError(
            "travel_routes.json muss "
            "ein JSON-Objekt enthalten."
        )

    if not travel_stations:
        raise ValueError(
            "travel_stations.json ist leer."
        )

    if not route_patterns:
        raise ValueError(
            "route_patterns.json ist leer."
        )

    if not travel_routes:
        raise ValueError(
            "travel_routes.json ist leer."
        )


def print_summary(
    travel_stations: dict[str, Any],
    route_patterns: dict[str, Any],
    travel_routes: dict[str, Any],
) -> None:
    print("=" * 72)
    print("TRAVEL-GRAPH: EINGABEDATEN GELADEN")
    print("=" * 72)

    print(
        f"Travel-Stationen: "
        f"{len(travel_stations):,}"
    )

    print(
        f"Route-Patterns:   "
        f"{len(route_patterns):,}"
    )

    print(
        f"Travel-Routen:    "
        f"{len(travel_routes):,}"
    )

    example_pattern = next(
        iter(
            route_patterns.values()
        )
    )

    print("\nBeispiel-Pattern:")

    print(
        f"- ID: "
        f"{example_pattern.get('id', '')}"
    )

    print(
        f"- Route: "
        f"{example_pattern.get('route_id', '')}"
    )

    print(
        f"- Richtung: "
        f"{example_pattern.get('direction_id', '')}"
    )

    print(
        f"- Ziel: "
        f"{example_pattern.get('headsign', '')}"
    )

    print(
        f"- Stationen: "
        f"{example_pattern.get('station_count', 0)}"
    )

    print(
        "\nAlle Eingabedateien sehen "
        "grundsätzlich gültig aus."
    )


def build_graph_edges(
    route_patterns: dict[str, Any],
    travel_routes: dict[str, Any],
    travel_stations: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
]:
    """
    Erzeugt gerichtete Verbindungen zwischen
    direkt aufeinanderfolgenden Stationen.

    Beispiel:

    Esslingen → Mettingen → Obertürkheim

    wird zu:

    Esslingen → Mettingen
    Mettingen → Obertürkheim
    """

    edge_groups: dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ] = {}

    skipped_patterns = 0
    skipped_connections = 0

    for (
        pattern_id,
        pattern,
    ) in route_patterns.items():
        route_id = normalize_text(
            pattern.get("route_id")
        )

        route = travel_routes.get(
            route_id
        )

        if not route:
            skipped_patterns += 1
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
            skipped_patterns += 1
            continue

        direction_id = normalize_text(
            pattern.get("direction_id")
        )

        headsign = normalize_text(
            pattern.get("headsign")
        )

        trip_count = int(
            pattern.get(
                "trip_count",
                0,
            )
            or 0
        )

        for sequence_index in range(
            len(station_ids) - 1
        ):
            from_station_id = (
                station_ids[
                    sequence_index
                ]
            )

            to_station_id = (
                station_ids[
                    sequence_index + 1
                ]
            )

            if (
                from_station_id
                == to_station_id
            ):
                skipped_connections += 1
                continue

            if (
                from_station_id
                not in travel_stations
                or to_station_id
                not in travel_stations
            ):
                skipped_connections += 1
                continue

            edge_key = (
                from_station_id,
                to_station_id,
                route_id,
                direction_id,
            )

            if (
                edge_key
                not in edge_groups
            ):
                edge_groups[
                    edge_key
                ] = {
                    "from": from_station_id,
                    "to": to_station_id,
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
                    "pattern_ids": set(),
                    "trip_count": 0,
                }

            edge = edge_groups[
                edge_key
            ]

            edge[
                "pattern_ids"
            ].add(
                pattern_id
            )

            if headsign:
                edge[
                    "headsigns"
                ].add(
                    headsign
                )

            edge[
                "trip_count"
            ] += trip_count

    graph: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    station_route_groups: dict[
        str,
        dict[
            str,
            dict[str, Any],
        ],
    ] = defaultdict(dict)

    review_rows: list[
        dict[str, Any]
    ] = []

    sorted_edges = sorted(
        edge_groups.values(),
        key=lambda edge: (
            edge["from"],
            edge["route_short_name"],
            edge["to"],
            edge["direction_id"],
        ),
    )

    for edge in sorted_edges:
        headsigns = sorted(
            edge["headsigns"]
        )

        pattern_ids = sorted(
            edge["pattern_ids"]
        )

        graph_edge = {
            "to": edge["to"],
            "route_id": (
                edge["route_id"]
            ),
            "route_short_name": (
                edge["route_short_name"]
            ),
            "route_long_name": (
                edge["route_long_name"]
            ),
            "route_type": (
                edge["route_type"]
            ),
            "direction_id": (
                edge["direction_id"]
            ),
            "headsigns": headsigns,
            "pattern_ids": pattern_ids,
            "trip_count": (
                edge["trip_count"]
            ),
        }

        graph[
            edge["from"]
        ].append(
            graph_edge
        )

        route_id = edge[
            "route_id"
        ]

        if (
            route_id
            not in station_route_groups[
                edge["from"]
            ]
        ):
            station_route_groups[
                edge["from"]
            ][
                route_id
            ] = {
                "route_id": route_id,
                "short_name": (
                    edge[
                        "route_short_name"
                    ]
                ),
                "long_name": (
                    edge[
                        "route_long_name"
                    ]
                ),
                "route_type": (
                    edge[
                        "route_type"
                    ]
                ),
                "headsigns": set(),
                "reachable_station_ids": set(),
            }

        station_route_entry = (
            station_route_groups[
                edge["from"]
            ][
                route_id
            ]
        )

        station_route_entry[
            "reachable_station_ids"
        ].add(
            edge["to"]
        )

        station_route_entry[
            "headsigns"
        ].update(
            headsigns
        )

        from_station_name = (
            travel_stations[
                edge["from"]
            ].get(
                "name",
                edge["from"],
            )
        )

        to_station_name = (
            travel_stations[
                edge["to"]
            ].get(
                "name",
                edge["to"],
            )
        )

        review_rows.append(
            {
                "from_station_id": (
                    edge["from"]
                ),
                "from_station_name": (
                    from_station_name
                ),
                "to_station_id": (
                    edge["to"]
                ),
                "to_station_name": (
                    to_station_name
                ),
                "route_id": (
                    edge["route_id"]
                ),
                "route_short_name": (
                    edge[
                        "route_short_name"
                    ]
                ),
                "route_long_name": (
                    edge[
                        "route_long_name"
                    ]
                ),
                "route_type": (
                    edge["route_type"]
                ),
                "direction_id": (
                    edge[
                        "direction_id"
                    ]
                ),
                "headsigns": (
                    " | ".join(
                        headsigns
                    )
                ),
                "pattern_count": len(
                    pattern_ids
                ),
                "trip_count": (
                    edge["trip_count"]
                ),
            }
        )

    station_routes: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for (
        station_id,
        route_entries,
    ) in station_route_groups.items():
        station_routes[
            station_id
        ] = []

        sorted_route_entries = sorted(
            route_entries.values(),
            key=lambda entry: (
                entry["short_name"],
                entry["route_id"],
            ),
        )

        for (
            route_entry
        ) in sorted_route_entries:
            station_routes[
                station_id
            ].append(
                {
                    "route_id": (
                        route_entry[
                            "route_id"
                        ]
                    ),
                    "short_name": (
                        route_entry[
                            "short_name"
                        ]
                    ),
                    "long_name": (
                        route_entry[
                            "long_name"
                        ]
                    ),
                    "route_type": (
                        route_entry[
                            "route_type"
                        ]
                    ),
                    "headsigns": sorted(
                        route_entry[
                            "headsigns"
                        ]
                    ),
                    "next_station_ids": sorted(
                        route_entry[
                            "reachable_station_ids"
                        ]
                    ),
                }
            )

    print("\nGraph-Erstellung:")

    print(
        "- Eindeutige gerichtete Kanten: "
        f"{len(sorted_edges):,}"
    )

    print(
        "- Stationen mit ausgehenden Kanten: "
        f"{len(graph):,}"
    )

    print(
        "- Übersprungene Patterns: "
        f"{skipped_patterns:,}"
    )

    print(
        "- Übersprungene Verbindungen: "
        f"{skipped_connections:,}"
    )

    return (
        dict(graph),
        station_routes,
        review_rows,
    )


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


def save_graph_results(
    graph: dict[str, Any],
    station_routes: dict[str, Any],
    review_rows: list[dict[str, Any]],
) -> None:
    save_json(
        OUTPUT_GRAPH_JSON,
        graph,
    )

    save_json(
        OUTPUT_STATION_ROUTES_JSON,
        station_routes,
    )

    pd.DataFrame(
        review_rows
    ).to_csv(
        OUTPUT_REVIEW_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def print_graph_examples(
    graph: dict[str, Any],
    travel_stations: dict[str, Any],
) -> None:
    example_station_names = [
        "Marienplatz",
        "Esslingen (N)",
        "Vaihingen",
        "Hauptbahnhof (tief)",
    ]

    print(
        "\nBeispiel-Verbindungen:"
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
            ) == station_name
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

        outgoing_edges = graph.get(
            station_id,
            [],
        )

        if not outgoing_edges:
            print(
                "- keine ausgehenden Verbindungen"
            )
            continue

        for edge in outgoing_edges[:15]:
            target_station = (
                travel_stations.get(
                    edge["to"],
                    {},
                )
            )

            target_name = (
                target_station.get(
                    "name",
                    edge["to"],
                )
            )

            headsign_text = (
                ", ".join(
                    edge[
                        "headsigns"
                    ][:2]
                )
                or "ohne Zielangabe"
            )

            print(
                "- "
                f"{edge['route_short_name']} "
                f"→ {target_name} "
                f"| Richtung: "
                f"{headsign_text}"
            )


def main() -> None:
    travel_stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    route_patterns = load_json(
        ROUTE_PATTERNS_FILE
    )

    travel_routes = load_json(
        TRAVEL_ROUTES_FILE
    )

    validate_input_data(
        travel_stations,
        route_patterns,
        travel_routes,
    )

    print_summary(
        travel_stations,
        route_patterns,
        travel_routes,
    )

    (
        graph,
        station_routes,
        review_rows,
    ) = build_graph_edges(
        route_patterns,
        travel_routes,
        travel_stations,
    )

    save_graph_results(
        graph,
        station_routes,
        review_rows,
    )

    print(
        "\nAusgabedateien:"
    )

    print(
        f"- Graph:\n"
        f"  {OUTPUT_GRAPH_JSON}"
    )

    print(
        "- Stations-Linien-Index:\n"
        f"  {OUTPUT_STATION_ROUTES_JSON}"
    )

    print(
        "- Kontroll-CSV:\n"
        f"  {OUTPUT_REVIEW_CSV}"
    )

    print_graph_examples(
        graph,
        travel_stations,
    )


if __name__ == "__main__":
    main()