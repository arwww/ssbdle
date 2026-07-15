from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "output"
)

MODE_ID = "stuttgart-rail"
MODE_NAME = "Stuttgart S- & U-Bahn"

STUTTGART_STATION_PREFIX = (
    "de:08111:"
)

ALLOWED_ROUTE_TYPES = {
    "109",  # S-Bahn
    "402",  # Stadtbahn / U-Bahn
}


TRAVEL_STATIONS_FILE = (
    OUTPUT_DIR
    / "travel_stations.json"
)

WEIGHTED_GRAPH_FILE = (
    OUTPUT_DIR
    / "weighted_travel_graph.json"
)

TRAVEL_MOVE_INDEX_FILE = (
    OUTPUT_DIR
    / "travel_move_index.json"
)


WEB_MODE_DIR = (
    PROJECT_ROOT
    / "web"
    / "data"
    / "travel"
    / MODE_ID
)

WEB_STATIONS_FILE = (
    WEB_MODE_DIR
    / "stations.json"
)

WEB_GRAPH_FILE = (
    WEB_MODE_DIR
    / "graph.json"
)

WEB_MOVES_FILE = (
    WEB_MODE_DIR
    / "moves.json"
)

WEB_MANIFEST_FILE = (
    WEB_MODE_DIR
    / "manifest.json"
)


def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def parse_integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(
            round(
                float(value)
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return default


def parse_number(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None


def load_json(
    path: Path,
) -> Any:
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


def is_stuttgart_station(
    station_id: str,
) -> bool:
    return normalize_text(
        station_id
    ).startswith(
        STUTTGART_STATION_PREFIX
    )


def is_allowed_route_type(
    route_type: Any,
) -> bool:
    return normalize_text(
        route_type
    ) in ALLOWED_ROUTE_TYPES


def collect_mode_station_ids(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    weighted_graph: dict[
        str,
        list[dict[str, Any]],
    ],
) -> tuple[
    set[str],
    dict[str, int],
]:
    """
    Nimmt nur Stuttgarter Stationen auf, die tatsächlich
    von einer erlaubten S-Bahn- oder Stadtbahnverbindung
    bedient werden.

    Reine Bushaltestellen werden dadurch nicht exportiert.
    """

    station_ids: set[str] = set()

    statistics = {
        "source_ride_edges": 0,
        "accepted_ride_edges": 0,
        "rejected_route_type": 0,
        "rejected_outside_stuttgart": 0,
        "rejected_unknown_station": 0,
    }

    for (
        from_station_id,
        edges,
    ) in weighted_graph.items():
        from_station_id = (
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
                or "ride"
            )

            if edge_type != "ride":
                continue

            statistics[
                "source_ride_edges"
            ] += 1

            route_type = (
                normalize_text(
                    edge.get(
                        "route_type"
                    )
                )
            )

            if not is_allowed_route_type(
                route_type
            ):
                statistics[
                    "rejected_route_type"
                ] += 1

                continue

            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            if (
                not is_stuttgart_station(
                    from_station_id
                )
                or not is_stuttgart_station(
                    to_station_id
                )
            ):
                statistics[
                    "rejected_outside_stuttgart"
                ] += 1

                continue

            if (
                from_station_id
                not in travel_stations
                or to_station_id
                not in travel_stations
            ):
                statistics[
                    "rejected_unknown_station"
                ] += 1

                continue

            station_ids.add(
                from_station_id
            )

            station_ids.add(
                to_station_id
            )

            statistics[
                "accepted_ride_edges"
            ] += 1

    if not station_ids:
        raise ValueError(
            "Es wurden keine Stuttgarter "
            "S- oder U-Bahn-Stationen gefunden."
        )

    return (
        station_ids,
        statistics,
    )


def build_web_stations(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
    allowed_station_ids: set[str],
) -> dict[str, Any]:
    station_rows: list[
        dict[str, Any]
    ] = []

    for station_id in (
        allowed_station_ids
    ):
        station = (
            travel_stations[
                station_id
            ]
        )

        name = (
            normalize_text(
                station.get("name")
            )
            or station_id
        )

        latitude = parse_number(
            station.get(
                "latitude"
            )
        )

        longitude = parse_number(
            station.get(
                "longitude"
            )
        )

        station_row: dict[
            str,
            Any,
        ] = {
            "id": station_id,
            "name": name,
        }

        if latitude is not None:
            station_row[
                "latitude"
            ] = latitude

        if longitude is not None:
            station_row[
                "longitude"
            ] = longitude

        station_rows.append(
            station_row
        )

    station_rows.sort(
        key=lambda station: (
            station["name"].casefold(),
            station["id"],
        )
    )

    return {
        "metadata": {
            "mode": MODE_ID,
            "station_count": len(
                station_rows
            ),
        },
        "stations": station_rows,
    }


def build_web_graph(
    weighted_graph: dict[
        str,
        list[dict[str, Any]],
    ],
    allowed_station_ids: set[str],
) -> dict[str, Any]:
    adjacency: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    ride_edge_count = 0
    transfer_edge_count = 0

    for from_station_id in sorted(
        allowed_station_ids
    ):
        source_edges = (
            weighted_graph.get(
                from_station_id,
                [],
            )
        )

        compact_edges: list[
            dict[str, Any]
        ] = []

        for edge in source_edges:
            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            if (
                not to_station_id
                or to_station_id
                not in allowed_station_ids
            ):
                continue

            edge_type = (
                normalize_text(
                    edge.get(
                        "edge_type"
                    )
                )
                or "ride"
            )

            travel_time_seconds = (
                parse_integer(
                    edge.get(
                        "travel_time_seconds"
                    ),
                    120,
                )
            )

            if edge_type == "transfer":
                compact_edges.append(
                    {
                        "to": to_station_id,
                        "type": "transfer",
                        "time": (
                            travel_time_seconds
                        ),
                    }
                )

                transfer_edge_count += 1
                continue

            route_type = (
                normalize_text(
                    edge.get(
                        "route_type"
                    )
                )
            )

            if not is_allowed_route_type(
                route_type
            ):
                continue

            route_id = (
                normalize_text(
                    edge.get(
                        "route_id"
                    )
                )
            )

            if not route_id:
                continue

            compact_edges.append(
                {
                    "to": to_station_id,
                    "type": "ride",
                    "routeId": route_id,
                    "line": normalize_text(
                        edge.get(
                            "route_short_name"
                        )
                    ),
                    "routeType": (
                        route_type
                    ),
                    "directionId": (
                        normalize_text(
                            edge.get(
                                "direction_id"
                            )
                        )
                    ),
                    "time": (
                        travel_time_seconds
                    ),
                }
            )

            ride_edge_count += 1

        compact_edges.sort(
            key=lambda edge: (
                0
                if edge["type"] == "ride"
                else 1,
                normalize_text(
                    edge.get("line")
                ),
                edge["to"],
            )
        )

        if compact_edges:
            adjacency[
                from_station_id
            ] = compact_edges

    return {
        "metadata": {
            "mode": MODE_ID,
            "node_count": len(
                adjacency
            ),
            "ride_edge_count": (
                ride_edge_count
            ),
            "transfer_edge_count": (
                transfer_edge_count
            ),
        },
        "adjacency": adjacency,
    }


def build_web_moves(
    travel_move_index: dict[
        str,
        Any,
    ],
    allowed_station_ids: set[str],
) -> dict[str, Any]:
    source_station_moves = (
        travel_move_index.get(
            "station_moves",
            {},
        )
    )

    compact_station_moves: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    service_count = 0
    destination_count = 0

    for station_id in sorted(
        allowed_station_ids
    ):
        station_entry = (
            source_station_moves.get(
                station_id
            )
        )

        if not station_entry:
            continue

        compact_services: list[
            dict[str, Any]
        ] = []

        for service in (
            station_entry.get(
                "services",
                [],
            )
        ):
            route_type = (
                normalize_text(
                    service.get(
                        "route_type"
                    )
                )
            )

            if not is_allowed_route_type(
                route_type
            ):
                continue

            route_id = (
                normalize_text(
                    service.get(
                        "route_id"
                    )
                )
            )

            direction_id = (
                normalize_text(
                    service.get(
                        "direction_id"
                    )
                )
            )

            service_key = (
                normalize_text(
                    service.get(
                        "service_key"
                    )
                )
                or (
                    f"{route_id}"
                    f"::{direction_id}"
                )
            )

            if (
                not route_id
                or not service_key
            ):
                continue

            compact_destinations: list[
                dict[str, Any]
            ] = []

            for destination in (
                service.get(
                    "destinations",
                    [],
                )
            ):
                destination_station_id = (
                    normalize_text(
                        destination.get(
                            "station_id"
                        )
                    )
                )

                if (
                    not destination_station_id
                    or destination_station_id
                    not in allowed_station_ids
                ):
                    continue

                compact_destinations.append(
                    {
                        "stationId": (
                            destination_station_id
                        ),
                        "time": parse_integer(
                            destination.get(
                                "travel_time_seconds"
                            ),
                            120,
                        ),
                        "stops": parse_integer(
                            destination.get(
                                "stop_count"
                            ),
                            1,
                        ),
                    }
                )

            if not compact_destinations:
                continue

            compact_destinations.sort(
                key=lambda destination: (
                    destination["stops"],
                    destination["time"],
                    destination[
                        "stationId"
                    ],
                )
            )

            headsigns = [
                normalize_text(
                    headsign
                )
                for headsign
                in service.get(
                    "headsigns",
                    [],
                )
                if normalize_text(
                    headsign
                )
            ]

            compact_services.append(
                {
                    "serviceKey": (
                        service_key
                    ),
                    "routeId": (
                        route_id
                    ),
                    "line": normalize_text(
                        service.get(
                            "route_short_name"
                        )
                    ),
                    "routeType": (
                        route_type
                    ),
                    "directionId": (
                        direction_id
                    ),
                    "headsigns": (
                        headsigns
                    ),
                    "destinations": (
                        compact_destinations
                    ),
                }
            )

            service_count += 1
            destination_count += len(
                compact_destinations
            )

        compact_services.sort(
            key=lambda service: (
                service["line"],
                service[
                    "directionId"
                ],
                service[
                    "routeId"
                ],
            )
        )

        if compact_services:
            compact_station_moves[
                station_id
            ] = compact_services

    return {
        "metadata": {
            "mode": MODE_ID,
            "station_count": len(
                compact_station_moves
            ),
            "service_count": (
                service_count
            ),
            "destination_count": (
                destination_count
            ),
        },
        "stationMoves": (
            compact_station_moves
        ),
    }


def validate_export(
    web_stations: dict[str, Any],
    web_graph: dict[str, Any],
    web_moves: dict[str, Any],
) -> None:
    station_ids = {
        station["id"]
        for station
        in web_stations["stations"]
    }

    for (
        from_station_id,
        edges,
    ) in web_graph[
        "adjacency"
    ].items():
        if (
            from_station_id
            not in station_ids
        ):
            raise ValueError(
                "Graph enthält unbekannte "
                f"Ausgangsstation: {from_station_id}"
            )

        for edge in edges:
            if edge["to"] not in station_ids:
                raise ValueError(
                    "Graph enthält unbekannte "
                    f"Zielstation: {edge['to']}"
                )

            if (
                edge["type"] == "ride"
                and edge.get(
                    "routeType"
                )
                not in ALLOWED_ROUTE_TYPES
            ):
                raise ValueError(
                    "Graph enthält einen "
                    "nicht erlaubten Verkehrstyp."
                )

    for (
        station_id,
        services,
    ) in web_moves[
        "stationMoves"
    ].items():
        if station_id not in station_ids:
            raise ValueError(
                "Move-Index enthält unbekannte "
                f"Station: {station_id}"
            )

        for service in services:
            if (
                service[
                    "routeType"
                ]
                not in ALLOWED_ROUTE_TYPES
            ):
                raise ValueError(
                    "Move-Index enthält einen "
                    "nicht erlaubten Verkehrstyp."
                )

            for destination in (
                service[
                    "destinations"
                ]
            ):
                if (
                    destination[
                        "stationId"
                    ]
                    not in station_ids
                ):
                    raise ValueError(
                        "Move-Index enthält eine "
                        "unbekannte Zielstation."
                    )


def get_file_size_bytes(
    path: Path,
) -> int:
    if not path.exists():
        return 0

    return path.stat().st_size


def format_file_size(
    size_bytes: int,
) -> str:
    size = float(
        size_bytes
    )

    units = [
        "B",
        "KB",
        "MB",
        "GB",
    ]

    unit_index = 0

    while (
        size >= 1024
        and unit_index
        < len(units) - 1
    ):
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return (
            f"{int(size)} "
            f"{units[unit_index]}"
        )

    return (
        f"{size:.1f} "
        f"{units[unit_index]}"
    )


def print_examples(
    web_stations: dict[str, Any],
    web_moves: dict[str, Any],
) -> None:
    station_name_by_id = {
        station["id"]: station["name"]
        for station
        in web_stations["stations"]
    }

    example_names = [
        "Olgaeck",
        "Marienplatz",
        "Hauptbahnhof (tief)",
        "Zuffenhausen",
    ]

    print(
        "\nBeispielstationen:"
    )

    for example_name in (
        example_names
    ):
        matching_ids = [
            station_id
            for (
                station_id,
                station_name,
            ) in station_name_by_id.items()
            if station_name.casefold()
            == example_name.casefold()
        ]

        print(
            f"\n{example_name}:"
        )

        if not matching_ids:
            print(
                "- im Modus nicht enthalten"
            )
            continue

        station_id = (
            matching_ids[0]
        )

        services = (
            web_moves[
                "stationMoves"
            ].get(
                station_id,
                [],
            )
        )

        if not services:
            print(
                "- keine Spielzüge"
            )
            continue

        line_names = sorted({
            service["line"]
            or service["routeId"]
            for service in services
        })

        print(
            "- Linien: "
            + ", ".join(
                line_names
            )
        )

        print(
            "- Linien-/Richtungsoptionen: "
            f"{len(services)}"
        )


def main() -> None:
    print("=" * 72)
    print("STUTTGART S- & U-BAHN WEB-DATEN EXPORTIEREN")
    print("=" * 72)

    travel_stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    weighted_graph = load_json(
        WEIGHTED_GRAPH_FILE
    )

    travel_move_index = load_json(
        TRAVEL_MOVE_INDEX_FILE
    )

    if not isinstance(
        travel_stations,
        dict,
    ):
        raise ValueError(
            "travel_stations.json ist ungültig."
        )

    if not isinstance(
        weighted_graph,
        dict,
    ):
        raise ValueError(
            "weighted_travel_graph.json ist ungültig."
        )

    if not isinstance(
        travel_move_index,
        dict,
    ):
        raise ValueError(
            "travel_move_index.json ist ungültig."
        )

    print(
        f"Quellstationen:                  "
        f"{len(travel_stations):,}"
    )

    print(
        f"Quellknoten im Graph:            "
        f"{len(weighted_graph):,}"
    )

    (
        allowed_station_ids,
        filter_statistics,
    ) = collect_mode_station_ids(
        travel_stations,
        weighted_graph,
    )

    print(
        f"Stuttgarter Bahnstationen:       "
        f"{len(allowed_station_ids):,}"
    )

    print(
        f"Akzeptierte Bahn-Fahrkanten:     "
        f"{filter_statistics['accepted_ride_edges']:,}"
    )

    print(
        f"Ausgeschlossene Verkehrstypen:   "
        f"{filter_statistics['rejected_route_type']:,}"
    )

    print(
        f"Außerhalb Stuttgarts:            "
        f"{filter_statistics['rejected_outside_stuttgart']:,}"
    )

    web_stations = (
        build_web_stations(
            travel_stations,
            allowed_station_ids,
        )
    )

    web_graph = (
        build_web_graph(
            weighted_graph,
            allowed_station_ids,
        )
    )

    web_moves = (
        build_web_moves(
            travel_move_index,
            allowed_station_ids,
        )
    )

    validate_export(
        web_stations,
        web_graph,
        web_moves,
    )

    save_compact_json(
        WEB_STATIONS_FILE,
        web_stations,
    )

    save_compact_json(
        WEB_GRAPH_FILE,
        web_graph,
    )

    save_compact_json(
        WEB_MOVES_FILE,
        web_moves,
    )

    manifest = {
        "version": 1,
        "mode": {
            "id": MODE_ID,
            "name": MODE_NAME,
            "enabled": True,
            "area": "Stuttgart",
            "station_id_prefix": (
                STUTTGART_STATION_PREFIX
            ),
            "route_types": sorted(
                ALLOWED_ROUTE_TYPES
            ),
        },
        "files": {
            "stations": (
                "stations.json"
            ),
            "graph": (
                "graph.json"
            ),
            "moves": (
                "moves.json"
            ),
        },
        "counts": {
            "stations": (
                web_stations[
                    "metadata"
                ][
                    "station_count"
                ]
            ),
            "graphNodes": (
                web_graph[
                    "metadata"
                ][
                    "node_count"
                ]
            ),
            "rideEdges": (
                web_graph[
                    "metadata"
                ][
                    "ride_edge_count"
                ]
            ),
            "transferEdges": (
                web_graph[
                    "metadata"
                ][
                    "transfer_edge_count"
                ]
            ),
            "moveStations": (
                web_moves[
                    "metadata"
                ][
                    "station_count"
                ]
            ),
            "services": (
                web_moves[
                    "metadata"
                ][
                    "service_count"
                ]
            ),
            "destinations": (
                web_moves[
                    "metadata"
                ][
                    "destination_count"
                ]
            ),
        },
    }

    save_compact_json(
        WEB_MANIFEST_FILE,
        manifest,
    )

    print(
        "\n" + "=" * 72
    )

    print(
        "STUTTGART-RAIL-EXPORT ERFOLGREICH"
    )

    print("=" * 72)

    print(
        "Exportierte Stationen:          "
        f"{web_stations['metadata']['station_count']:,}"
    )

    print(
        "Graph-Knoten:                   "
        f"{web_graph['metadata']['node_count']:,}"
    )

    print(
        "Fahrkanten:                     "
        f"{web_graph['metadata']['ride_edge_count']:,}"
    )

    print(
        "Transferkanten:                 "
        f"{web_graph['metadata']['transfer_edge_count']:,}"
    )

    print(
        "Stationen mit Spielzügen:       "
        f"{web_moves['metadata']['station_count']:,}"
    )

    print(
        "Linien-/Richtungsoptionen:      "
        f"{web_moves['metadata']['service_count']:,}"
    )

    print(
        "Legale Ausstiegsoptionen:       "
        f"{web_moves['metadata']['destination_count']:,}"
    )

    print(
        "\nExportierte Dateien:"
    )

    for path in [
        WEB_STATIONS_FILE,
        WEB_GRAPH_FILE,
        WEB_MOVES_FILE,
        WEB_MANIFEST_FILE,
    ]:
        relative_path = path.relative_to(
            PROJECT_ROOT
        )

        print(
            f"- {relative_path} "
            f"— {format_file_size(get_file_size_bytes(path))}"
        )

    print_examples(
        web_stations,
        web_moves,
    )


if __name__ == "__main__":
    main()