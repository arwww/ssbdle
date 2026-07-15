from __future__ import annotations

import heapq
import json
from itertools import count
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRAVEL_STATIONS_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_stations.json"
)

WEIGHTED_GRAPH_FILE = (
    PROJECT_ROOT
    / "output"
    / "weighted_travel_graph.json"
)


# Diese Zeit wird angenommen, wenn zwei Linien an derselben
# logischen Station gewechselt werden und keine explizite
# Fußwegkante aus transfers.txt vorhanden ist.
SAME_STATION_TRANSFER_TIME_SECONDS = 180


# Diese Zeit ist keine reale Reisezeit, sondern eine zusätzliche
# Komfortstrafe für die Routenauswahl. Dadurch vermeidet der
# Router unnötig viele Umstiege.
TRANSFER_PENALTY_SECONDS = 300


DEFAULT_RIDE_TIME_SECONDS = 120
DEFAULT_TRANSFER_TIME_SECONDS = 180

START_SERVICE = "__start__"
WALK_SERVICE = "__walk__"


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
    return str(
        value or ""
    ).strip()


def normalize_search_text(value: Any) -> str:
    return normalize_text(
        value
    ).casefold()


def parse_seconds(
    value: Any,
    default: int,
) -> int:
    try:
        seconds = int(
            round(
                float(value)
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return default

    if seconds < 0:
        return default

    return seconds


def format_minutes(
    seconds: int,
) -> str:
    minutes = seconds / 60

    if seconds % 60 == 0:
        return (
            f"{int(minutes)} Min."
        )

    return (
        f"{minutes:.1f} Min."
    )


def get_station_name(
    stations: dict[
        str,
        dict[str, Any],
    ],
    station_id: str,
) -> str:
    return normalize_text(
        stations.get(
            station_id,
            {},
        ).get(
            "name",
            station_id,
        )
    ) or station_id


def find_station_ids_by_name(
    stations: dict[
        str,
        dict[str, Any],
    ],
    search_name: str,
) -> list[str]:
    normalized_search = (
        normalize_search_text(
            search_name
        )
    )

    exact_matches = [
        station_id
        for (
            station_id,
            station,
        ) in stations.items()
        if normalize_search_text(
            station.get("name")
        ) == normalized_search
    ]

    if exact_matches:
        return sorted(
            exact_matches
        )

    partial_matches = [
        station_id
        for (
            station_id,
            station,
        ) in stations.items()
        if normalized_search
        in normalize_search_text(
            station.get("name")
        )
    ]

    return sorted(
        partial_matches,
        key=lambda station_id: (
            get_station_name(
                stations,
                station_id,
            ).casefold(),
            station_id,
        ),
    )


def choose_station_id(
    stations: dict[
        str,
        dict[str, Any],
    ],
    search_name: str,
) -> str:
    matches = (
        find_station_ids_by_name(
            stations,
            search_name,
        )
    )

    if not matches:
        raise ValueError(
            f"Keine Station für "
            f"„{search_name}“ gefunden."
        )

    if len(matches) == 1:
        return matches[0]

    print(
        f"\nMehrere Treffer für "
        f"„{search_name}“:"
    )

    for index, station_id in enumerate(
        matches,
        start=1,
    ):
        print(
            f"{index}. "
            f"{get_station_name(stations, station_id)} "
            f"[{station_id}]"
        )

    while True:
        user_input = input(
            "Nummer auswählen: "
        ).strip()

        try:
            selection = int(
                user_input
            )
        except ValueError:
            print(
                "Bitte eine Zahl eingeben."
            )
            continue

        if (
            1
            <= selection
            <= len(matches)
        ):
            return matches[
                selection - 1
            ]

        print(
            "Ungültige Auswahl."
        )


def make_service_key(
    edge: dict[str, Any],
) -> str:
    """
    Die Fahrtrichtung gehört zum Zustand.

    Dadurch kann der Router nicht kostenlos innerhalb derselben
    Linie die Richtung wechseln.
    """

    route_id = normalize_text(
        edge.get("route_id")
    )

    direction_id = normalize_text(
        edge.get("direction_id")
    )

    return (
        f"{route_id}::{direction_id}"
    )


def find_best_weighted_route(
    graph: dict[
        str,
        list[dict[str, Any]],
    ],
    start_station_id: str,
    target_station_id: str,
) -> tuple[
    dict[str, int] | None,
    list[dict[str, Any]],
]:
    """
    Dijkstra mit einem erweiterten Zustand:

    (aktuelle Station, aktuelle Linie und Richtung)

    Primär wird die sogenannte generalisierte Zeit minimiert:

    tatsächliche Reisezeit
    + geschätzte Umstiegszeit
    + Komfortstrafe je Umstieg
    """

    start_state = (
        start_station_id,
        START_SERVICE,
    )

    # Kostenreihenfolge:
    # 1. generalisierte Zeit
    # 2. Anzahl Umstiege
    # 3. tatsächliche Reisezeit
    # 4. Anzahl gefahrener Haltestellen
    start_cost = (
        0,
        0,
        0,
        0,
    )

    tie_breaker = count()

    queue: list[
        tuple[
            tuple[int, int, int, int],
            int,
            tuple[str, str],
        ]
    ] = [
        (
            start_cost,
            next(tie_breaker),
            start_state,
        )
    ]

    best_cost: dict[
        tuple[str, str],
        tuple[int, int, int, int],
    ] = {
        start_state: start_cost
    }

    predecessor: dict[
        tuple[str, str],
        tuple[
            tuple[str, str],
            dict[str, Any],
        ],
    ] = {}

    target_state: (
        tuple[str, str]
        | None
    ) = None

    while queue:
        (
            current_cost,
            _,
            current_state,
        ) = heapq.heappop(
            queue
        )

        if (
            current_cost
            != best_cost.get(
                current_state
            )
        ):
            continue

        (
            station_id,
            current_service,
        ) = current_state

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
            edge_type = normalize_text(
                edge.get("edge_type")
            )

            next_station_id = normalize_text(
                edge.get("to")
            )

            if not next_station_id:
                continue

            transfer_increment = 0
            transfer_penalty = 0
            same_station_transfer_time = 0
            ride_stop_increment = 0

            if edge_type == "transfer":
                edge_time_seconds = (
                    parse_seconds(
                        edge.get(
                            "travel_time_seconds"
                        ),
                        DEFAULT_TRANSFER_TIME_SECONDS,
                    )
                )

                # Der Umstieg wird beim Beginn des Fußwegs gezählt.
                # Weitere direkt folgende Fußwege erhöhen ihn nicht.
                if current_service not in {
                    START_SERVICE,
                    WALK_SERVICE,
                }:
                    transfer_increment = 1
                    transfer_penalty = (
                        TRANSFER_PENALTY_SECONDS
                    )

                next_service = (
                    WALK_SERVICE
                )

            else:
                edge_type = "ride"

                edge_time_seconds = (
                    parse_seconds(
                        edge.get(
                            "travel_time_seconds"
                        ),
                        DEFAULT_RIDE_TIME_SECONDS,
                    )
                )

                next_service = (
                    make_service_key(
                        edge
                    )
                )

                ride_stop_increment = 1

                # Erster Einstieg und Einstieg nach einem expliziten
                # Fußweg sind kein zusätzlicher Umstieg.
                if (
                    current_service
                    not in {
                        START_SERVICE,
                        WALK_SERVICE,
                    }
                    and current_service
                    != next_service
                ):
                    transfer_increment = 1

                    same_station_transfer_time = (
                        SAME_STATION_TRANSFER_TIME_SECONDS
                    )

                    transfer_penalty = (
                        TRANSFER_PENALTY_SECONDS
                    )

            added_actual_time = (
                edge_time_seconds
                + same_station_transfer_time
            )

            added_generalized_time = (
                added_actual_time
                + transfer_penalty
            )

            new_cost = (
                current_cost[0]
                + added_generalized_time,

                current_cost[1]
                + transfer_increment,

                current_cost[2]
                + added_actual_time,

                current_cost[3]
                + ride_stop_increment,
            )

            next_state = (
                next_station_id,
                next_service,
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
                {
                    **edge,
                    "from": station_id,
                    "edge_type": edge_type,
                    "edge_time_seconds": (
                        edge_time_seconds
                    ),
                    "added_actual_time_seconds": (
                        added_actual_time
                    ),
                    "same_station_transfer_time_seconds": (
                        same_station_transfer_time
                    ),
                    "transfer_penalty_seconds": (
                        transfer_penalty
                    ),
                    "transfer_increment": (
                        transfer_increment
                    ),
                },
            )

            heapq.heappush(
                queue,
                (
                    new_cost,
                    next(tie_breaker),
                    next_state,
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
            edge
        )

        current_state = (
            previous_state
        )

    path_edges.reverse()

    final_cost = best_cost[
        target_state
    ]

    result = {
        "generalized_time_seconds": (
            final_cost[0]
        ),
        "transfers": (
            final_cost[1]
        ),
        "actual_time_seconds": (
            final_cost[2]
        ),
        "ride_stops": (
            final_cost[3]
        ),
    }

    return (
        result,
        path_edges,
    )


def group_route_segments(
    path_edges: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    segments: list[
        dict[str, Any]
    ] = []

    for edge in path_edges:
        edge_type = normalize_text(
            edge.get("edge_type")
        )

        from_station_id = normalize_text(
            edge.get("from")
        )

        to_station_id = normalize_text(
            edge.get("to")
        )

        if edge_type == "transfer":
            if (
                segments
                and segments[-1][
                    "segment_type"
                ] == "transfer"
                and segments[-1][
                    "station_ids"
                ][-1] == from_station_id
            ):
                segment = segments[-1]

                segment[
                    "station_ids"
                ].append(
                    to_station_id
                )

                segment[
                    "time_seconds"
                ] += edge[
                    "edge_time_seconds"
                ]

                continue

            segments.append(
                {
                    "segment_type": (
                        "transfer"
                    ),
                    "station_ids": [
                        from_station_id,
                        to_station_id,
                    ],
                    "time_seconds": (
                        edge[
                            "edge_time_seconds"
                        ]
                    ),
                }
            )

            continue

        route_id = normalize_text(
            edge.get("route_id")
        )

        direction_id = normalize_text(
            edge.get("direction_id")
        )

        service_key = (
            route_id,
            direction_id,
        )

        can_extend_segment = (
            segments
            and segments[-1][
                "segment_type"
            ] == "ride"
            and segments[-1][
                "service_key"
            ] == service_key
            and segments[-1][
                "station_ids"
            ][-1] == from_station_id
            and edge[
                "same_station_transfer_time_seconds"
            ] == 0
        )

        if can_extend_segment:
            segment = segments[-1]

            segment[
                "station_ids"
            ].append(
                to_station_id
            )

            segment[
                "ride_time_seconds"
            ] += edge[
                "edge_time_seconds"
            ]

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
                "segment_type": "ride",
                "service_key": (
                    service_key
                ),
                "route_id": (
                    route_id
                ),
                "route_short_name": (
                    normalize_text(
                        edge.get(
                            "route_short_name"
                        )
                    )
                ),
                "route_long_name": (
                    normalize_text(
                        edge.get(
                            "route_long_name"
                        )
                    )
                ),
                "direction_id": (
                    direction_id
                ),
                "headsigns": set(
                    edge.get(
                        "headsigns",
                        [],
                    )
                ),
                "station_ids": [
                    from_station_id,
                    to_station_id,
                ],
                "ride_time_seconds": (
                    edge[
                        "edge_time_seconds"
                    ]
                ),
                "transfer_before_seconds": (
                    edge[
                        "same_station_transfer_time_seconds"
                    ]
                ),
                "stop_count": 1,
            }
        )

    for segment in segments:
        if (
            segment[
                "segment_type"
            ] == "ride"
        ):
            segment[
                "headsigns"
            ] = sorted(
                segment[
                    "headsigns"
                ]
            )

    return segments


def print_route(
    stations: dict[
        str,
        dict[str, Any],
    ],
    start_station_id: str,
    target_station_id: str,
    result: dict[str, int],
    segments: list[
        dict[str, Any]
    ],
) -> None:
    start_name = get_station_name(
        stations,
        start_station_id,
    )

    target_name = get_station_name(
        stations,
        target_station_id,
    )

    walking_seconds = sum(
        segment["time_seconds"]
        for segment in segments
        if segment[
            "segment_type"
        ] == "transfer"
    )

    print("\n" + "=" * 72)
    print("GEWICHTETE VERBINDUNG")
    print("=" * 72)

    print(
        f"Start: {start_name}"
    )

    print(
        f"Ziel:  {target_name}"
    )

    print(
        f"Geschätzte Reisezeit: "
        f"{format_minutes(result['actual_time_seconds'])}"
    )

    print(
        f"Umstiege: "
        f"{result['transfers']}"
    )

    print(
        f"Gefahrene Haltestellen: "
        f"{result['ride_stops']}"
    )

    print(
        f"Explizite Fußwege: "
        f"{format_minutes(walking_seconds)}"
    )

    print(
        f"Interner Routing-Score: "
        f"{format_minutes(result['generalized_time_seconds'])}"
    )

    print(
        "\nHinweis: Der Routing-Score enthält zusätzlich "
        "5 Minuten Komfortstrafe je Umstieg."
    )

    if not segments:
        print(
            "\nStart und Ziel sind identisch."
        )
        return

    print("\nRoute:")

    display_number = 1

    for segment in segments:
        if (
            segment[
                "segment_type"
            ] == "transfer"
        ):
            station_ids = (
                segment[
                    "station_ids"
                ]
            )

            from_name = get_station_name(
                stations,
                station_ids[0],
            )

            to_name = get_station_name(
                stations,
                station_ids[-1],
            )

            print(
                f"\n{display_number}. Fußweg"
            )

            print(
                f"   Von: {from_name}"
            )

            print(
                f"   Nach: {to_name}"
            )

            print(
                f"   Dauer: "
                f"{format_minutes(segment['time_seconds'])}"
            )

            display_number += 1
            continue

        station_ids = (
            segment[
                "station_ids"
            ]
        )

        boarding_name = (
            get_station_name(
                stations,
                station_ids[0],
            )
        )

        exit_name = (
            get_station_name(
                stations,
                station_ids[-1],
            )
        )

        transfer_before_seconds = (
            segment[
                "transfer_before_seconds"
            ]
        )

        if transfer_before_seconds > 0:
            print(
                f"\n{display_number}. Umstieg an "
                f"{boarding_name}"
            )

            print(
                "   Geschätzte Umstiegszeit: "
                f"{format_minutes(transfer_before_seconds)}"
            )

            display_number += 1

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

        station_names = [
            get_station_name(
                stations,
                station_id,
            )
            for station_id
            in station_ids
        ]

        print(
            f"\n{display_number}. Linie {line_name}"
        )

        print(
            f"   Einsteigen: {boarding_name}"
        )

        print(
            f"   Aussteigen: {exit_name}"
        )

        print(
            f"   Fahrzeit: "
            f"{format_minutes(segment['ride_time_seconds'])}"
        )

        print(
            f"   Haltestellen: "
            f"{segment['stop_count']}"
        )

        print(
            f"   Richtung: {headsign_text}"
        )

        print(
            "   Verlauf: "
            + " → ".join(
                station_names
            )
        )

        display_number += 1


def main() -> None:
    stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    graph = load_json(
        WEIGHTED_GRAPH_FILE
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
            "weighted_travel_graph.json ist ungültig."
        )

    print("=" * 72)
    print("SSBDLE WEIGHTED TRAVEL-ROUTING")
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
        result,
        path_edges,
    ) = find_best_weighted_route(
        graph,
        start_station_id,
        target_station_id,
    )

    if result is None:
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
        result,
        segments,
    )


if __name__ == "__main__":
    main()
    