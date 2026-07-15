from __future__ import annotations

import heapq
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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


def normalize_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def find_station_ids_by_name(
    stations: dict[str, dict[str, Any]],
    search_name: str,
) -> list[str]:
    normalized_search = normalize_text(
        search_name
    )

    exact_matches = [
        station_id
        for station_id, station
        in stations.items()
        if normalize_text(
            station.get("name")
        ) == normalized_search
    ]

    if exact_matches:
        return exact_matches

    return [
        station_id
        for station_id, station
        in stations.items()
        if normalized_search
        in normalize_text(
            station.get("name")
        )
    ]


def choose_station_id(
    stations: dict[str, dict[str, Any]],
    search_name: str,
) -> str:
    matches = find_station_ids_by_name(
        stations,
        search_name,
    )

    if not matches:
        raise ValueError(
            f"Keine Station für „{search_name}“ gefunden."
        )

    if len(matches) == 1:
        return matches[0]

    print(
        f"\nMehrere Treffer für „{search_name}“:"
    )

    for index, station_id in enumerate(
        matches,
        start=1,
    ):
        station = stations[
            station_id
        ]

        print(
            f"{index}. "
            f"{station.get('name', station_id)} "
            f"[{station_id}]"
        )

    while True:
        raw_choice = input(
            "Nummer auswählen: "
        ).strip()

        try:
            choice = int(raw_choice)
        except ValueError:
            print(
                "Bitte eine Zahl eingeben."
            )
            continue

        if (
            1 <= choice <= len(matches)
        ):
            return matches[
                choice - 1
            ]

        print(
            "Ungültige Auswahl."
        )


def route_cost(
    transfers: int,
    stops: int,
) -> tuple[int, int]:
    """
    Lexikografische Kosten:

    1. möglichst wenige Umstiege
    2. danach möglichst wenige Stationen
    """

    return (
        transfers,
        stops,
    )


def find_best_route(
    graph: dict[
        str,
        list[dict[str, Any]],
    ],
    start_station_id: str,
    target_station_id: str,
) -> tuple[
    tuple[int, int] | None,
    list[dict[str, Any]],
]:
    """
    Dijkstra über Zustände:

    (Station, aktuelle Route)

    Dadurch kann erkannt werden, ob die nächste
    Kante einen Umstieg verursacht.
    """

    start_state = (
        start_station_id,
        None,
    )

    queue: list[
        tuple[
            tuple[int, int],
            str,
            str | None,
        ]
    ] = [
        (
            route_cost(
                transfers=0,
                stops=0,
            ),
            start_station_id,
            None,
        )
    ]

    best_cost: dict[
        tuple[str, str | None],
        tuple[int, int],
    ] = {
        start_state: (
            0,
            0,
        )
    }

    predecessor: dict[
        tuple[str, str | None],
        tuple[
            tuple[str, str | None],
            dict[str, Any],
        ],
    ] = {}

    target_state: (
        tuple[str, str | None]
        | None
    ) = None

    while queue:
        (
            current_cost,
            station_id,
            current_route_id,
        ) = heapq.heappop(
            queue
        )

        current_state = (
            station_id,
            current_route_id,
        )

        if (
            current_cost
            != best_cost.get(
                current_state
            )
        ):
            continue

        if (
            station_id
            == target_station_id
        ):
            target_state = (
                current_state
            )
            break

        for edge in graph.get(
            station_id,
            [],
        ):
            next_station_id = str(
                edge["to"]
            )

            next_route_id = str(
                edge["route_id"]
            )

            changes_route = (
                current_route_id
                is not None
                and current_route_id
                != next_route_id
            )

            new_transfers = (
                current_cost[0]
                + (
                    1
                    if changes_route
                    else 0
                )
            )

            new_stops = (
                current_cost[1]
                + 1
            )

            new_cost = route_cost(
                transfers=new_transfers,
                stops=new_stops,
            )

            next_state = (
                next_station_id,
                next_route_id,
            )

            old_cost = best_cost.get(
                next_state
            )

            if (
                old_cost is not None
                and old_cost <= new_cost
            ):
                continue

            best_cost[
                next_state
            ] = new_cost

            predecessor[
                next_state
            ] = (
                current_state,
                edge,
            )

            heapq.heappush(
                queue,
                (
                    new_cost,
                    next_station_id,
                    next_route_id,
                ),
            )

    if target_state is None:
        return (
            None,
            [],
        )

    path_edges: list[
        dict[str, Any]
    ] = []

    current_state = (
        target_state
    )

    while (
        current_state
        != start_state
    ):
        (
            previous_state,
            edge,
        ) = predecessor[
            current_state
        ]

        path_edges.append(
            {
                "from": (
                    previous_state[0]
                ),
                **edge,
            }
        )

        current_state = (
            previous_state
        )

    path_edges.reverse()

    return (
        best_cost[
            target_state
        ],
        path_edges,
    )


def group_route_segments(
    path_edges: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    """
    Fasst direkt aufeinanderfolgende Kanten derselben
    route_id zu einem lesbaren Fahrtabschnitt zusammen.
    """

    segments: list[
        dict[str, Any]
    ] = []

    for edge in path_edges:
        route_id = str(
            edge["route_id"]
        )

        if (
            segments
            and segments[-1][
                "route_id"
            ] == route_id
        ):
            segment = segments[-1]

            segment[
                "station_ids"
            ].append(
                edge["to"]
            )

            segment[
                "stop_count"
            ] += 1

            segment[
                "headsigns"
            ].update(
                edge.get(
                    "headsigns",
                    [],
                )
            )

            continue

        segments.append(
            {
                "route_id": route_id,
                "route_short_name": (
                    edge.get(
                        "route_short_name",
                        "",
                    )
                ),
                "route_long_name": (
                    edge.get(
                        "route_long_name",
                        "",
                    )
                ),
                "route_type": (
                    edge.get(
                        "route_type",
                        "",
                    )
                ),
                "direction_id": (
                    edge.get(
                        "direction_id",
                        "",
                    )
                ),
                "headsigns": set(
                    edge.get(
                        "headsigns",
                        [],
                    )
                ),
                "station_ids": [
                    edge["from"],
                    edge["to"],
                ],
                "stop_count": 1,
            }
        )

    for segment in segments:
        segment[
            "headsigns"
        ] = sorted(
            segment["headsigns"]
        )

    return segments


def print_route(
    stations: dict[
        str,
        dict[str, Any],
    ],
    start_station_id: str,
    target_station_id: str,
    cost: tuple[int, int],
    segments: list[
        dict[str, Any]
    ],
) -> None:
    start_name = stations.get(
        start_station_id,
        {},
    ).get(
        "name",
        start_station_id,
    )

    target_name = stations.get(
        target_station_id,
        {},
    ).get(
        "name",
        target_station_id,
    )

    print("\n" + "=" * 72)
    print("GEFUNDENE VERBINDUNG")
    print("=" * 72)

    print(
        f"Start: {start_name}"
    )

    print(
        f"Ziel:  {target_name}"
    )

    print(
        f"Umstiege: {cost[0]}"
    )

    print(
        f"Gefahrene Stationen: "
        f"{cost[1]}"
    )

    print(
        f"Fahrtabschnitte: "
        f"{len(segments)}"
    )

    print("\nRoute:")

    for index, segment in enumerate(
        segments,
        start=1,
    ):
        station_ids = (
            segment[
                "station_ids"
            ]
        )

        boarding_name = (
            stations.get(
                station_ids[0],
                {},
            ).get(
                "name",
                station_ids[0],
            )
        )

        exit_name = (
            stations.get(
                station_ids[-1],
                {},
            ).get(
                "name",
                station_ids[-1],
            )
        )

        line_name = (
            segment[
                "route_short_name"
            ]
            or segment[
                "route_id"
            ]
        )

        headsign_text = (
            ", ".join(
                segment[
                    "headsigns"
                ][:3]
            )
            or "ohne Zielangabe"
        )

        print(
            f"\n{index}. Linie {line_name}"
        )

        print(
            f"   Einsteigen: {boarding_name}"
        )

        print(
            f"   Aussteigen: {exit_name}"
        )

        print(
            f"   Stationen: "
            f"{segment['stop_count']}"
        )

        print(
            f"   Richtung: "
            f"{headsign_text}"
        )

        station_names = [
            stations.get(
                station_id,
                {},
            ).get(
                "name",
                station_id,
            )
            for station_id
            in station_ids
        ]

        print(
            "   Verlauf: "
            + " → ".join(
                station_names
            )
        )


def main() -> None:
    stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    graph = load_json(
        TRAVEL_GRAPH_FILE
    )

    if not isinstance(
        stations,
        dict,
    ):
        raise ValueError(
            "travel_stations.json ist ungültig."
        )

    if not isinstance(
        graph,
        dict,
    ):
        raise ValueError(
            "travel_graph.json ist ungültig."
        )

    print("=" * 72)
    print("SSBDLE TRAVEL-ROUTING TEST")
    print("=" * 72)

    print(
        f"Stationen geladen: "
        f"{len(stations):,}"
    )

    print(
        f"Graph-Knoten geladen: "
        f"{len(graph):,}"
    )

    start_search = input(
        "\nStartstation: "
    ).strip()

    target_search = input(
        "Zielstation: "
    ).strip()

    start_station_id = (
        choose_station_id(
            stations,
            start_search,
        )
    )

    target_station_id = (
        choose_station_id(
            stations,
            target_search,
        )
    )

    (
        cost,
        path_edges,
    ) = find_best_route(
        graph,
        start_station_id,
        target_station_id,
    )

    if (
        cost is None
        or not path_edges
    ):
        print(
            "\nEs wurde keine Verbindung gefunden."
        )
        return

    segments = (
        group_route_segments(
            path_edges
        )
    )

    print_route(
        stations,
        start_station_id,
        target_station_id,
        cost,
        segments,
    )


if __name__ == "__main__":
    main()