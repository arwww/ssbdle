
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "output"
)

WEB_TRAVEL_DIR = (
    PROJECT_ROOT
    / "web"
    / "data"
    / "travel"
)

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

WEB_STATIONS_FILE = (
    WEB_TRAVEL_DIR
    / "stations.json"
)

WEB_GRAPH_FILE = (
    WEB_TRAVEL_DIR
    / "graph.json"
)

WEB_MOVES_FILE = (
    WEB_TRAVEL_DIR
    / "moves.json"
)

WEB_MANIFEST_FILE = (
    WEB_TRAVEL_DIR
    / "manifest.json"
)


def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


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


def build_web_stations(
    travel_stations: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    station_rows: list[
        dict[str, Any]
    ] = []

    for (
        station_id,
        station,
    ) in travel_stations.items():
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
) -> dict[str, Any]:
    adjacency: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    ride_edge_count = 0
    transfer_edge_count = 0

    for (
        from_station_id,
        edges,
    ) in weighted_graph.items():
        compact_edges: list[
            dict[str, Any]
        ] = []

        for edge in edges:
            edge_type = (
                normalize_text(
                    edge.get(
                        "edge_type"
                    )
                )
                or "ride"
            )

            to_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            if not to_station_id:
                continue

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
                        "to": (
                            to_station_id
                        ),
                        "type": (
                            "transfer"
                        ),
                        "time": (
                            travel_time_seconds
                        ),
                    }
                )

                transfer_edge_count += 1
                continue

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

            if not route_id:
                continue

            compact_edge = {
                "to": to_station_id,
                "type": "ride",
                "routeId": route_id,
                "line": (
                    normalize_text(
                        edge.get(
                            "route_short_name"
                        )
                    )
                ),
                "directionId": (
                    direction_id
                ),
                "time": (
                    travel_time_seconds
                ),
            }

            compact_edges.append(
                compact_edge
            )

            ride_edge_count += 1

        if compact_edges:
            adjacency[
                from_station_id
            ] = compact_edges

    return {
        "metadata": {
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

    for (
        station_id,
        station_entry,
    ) in source_station_moves.items():
        compact_services: list[
            dict[str, Any]
        ] = []

        for service in (
            station_entry.get(
                "services",
                [],
            )
        ):
            route_id = normalize_text(
                service.get(
                    "route_id"
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

                if not destination_station_id:
                    continue

                compact_destinations.append(
                    {
                        "stationId": (
                            destination_station_id
                        ),
                        "time": (
                            parse_integer(
                                destination.get(
                                    "travel_time_seconds"
                                ),
                                120,
                            )
                        ),
                        "stops": (
                            parse_integer(
                                destination.get(
                                    "stop_count"
                                ),
                                1,
                            )
                        ),
                    }
                )

                destination_count += 1

            if not compact_destinations:
                continue

            compact_services.append(
                {
                    "serviceKey": (
                        service_key
                    ),
                    "routeId": (
                        route_id
                    ),
                    "line": (
                        normalize_text(
                            service.get(
                                "route_short_name"
                            )
                        )
                    ),
                    "routeType": (
                        normalize_text(
                            service.get(
                                "route_type"
                            )
                        )
                    ),
                    "directionId": (
                        direction_id
                    ),
                    "headsigns": [
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
                    ],
                    "destinations": (
                        compact_destinations
                    ),
                }
            )

            service_count += 1

        if compact_services:
            compact_station_moves[
                station_id
            ] = compact_services

    return {
        "metadata": {
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


def main() -> None:
    print("=" * 72)
    print("TRAVEL-DATEN FÜR DAS WEB EXPORTIEREN")
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

    web_stations = (
        build_web_stations(
            travel_stations
        )
    )

    print(
        "Stationen vorbereitet:          "
        f"{web_stations['metadata']['station_count']:,}"
    )

    web_graph = build_web_graph(
        weighted_graph
    )

    print(
        "Graph-Knoten vorbereitet:       "
        f"{web_graph['metadata']['node_count']:,}"
    )

    print(
        "Fahrkanten vorbereitet:         "
        f"{web_graph['metadata']['ride_edge_count']:,}"
    )

    print(
        "Transferkanten vorbereitet:     "
        f"{web_graph['metadata']['transfer_edge_count']:,}"
    )

    web_moves = build_web_moves(
        travel_move_index
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
        "WEB-EXPORT ERFOLGREICH"
    )

    print("=" * 72)

    output_files = [
        WEB_STATIONS_FILE,
        WEB_GRAPH_FILE,
        WEB_MOVES_FILE,
        WEB_MANIFEST_FILE,
    ]

    for path in output_files:
        relative_path = (
            path.relative_to(
                PROJECT_ROOT
            )
        )

        size_text = (
            format_file_size(
                get_file_size_bytes(
                    path
                )
            )
        )

        print(
            f"{relative_path}"
            f" — {size_text}"
        )


if __name__ == "__main__":
    main()