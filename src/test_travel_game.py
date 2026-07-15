from __future__ import annotations

import heapq
import json
import re
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

MOVE_INDEX_FILE = (
    PROJECT_ROOT
    / "output"
    / "travel_move_index.json"
)


SAME_STATION_TRANSFER_TIME_SECONDS = 180
TRANSFER_PENALTY_SECONDS = 300

DEFAULT_RIDE_TIME_SECONDS = 120
DEFAULT_TRANSFER_TIME_SECONDS = 180

MAX_MOVES = 10

START_SERVICE = "__start__"
WALK_SERVICE = "__walk__"


RATING_SYMBOLS = {
    "green": "🟩",
    "yellow": "🟨",
    "orange": "🟧",
    "red": "🟥",
    "gray": "⬜",
}


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


def normalize_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def normalize_search_text(
    value: Any,
) -> str:
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


def natural_sort_key(
    value: Any,
) -> tuple[Any, ...]:
    parts = re.split(
        r"(\d+)",
        normalize_search_text(
            value
        ),
    )

    return tuple(
        (
            0,
            int(part),
        )
        if part.isdigit()
        else (
            1,
            part,
        )
        for part in parts
        if part
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


def find_station_ids_by_name(
    stations: dict[
        str,
        dict[str, Any],
    ],
    search_name: str,
) -> list[str]:
    search = (
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
        ) == search
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
        if search
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
        station_name = (
            get_station_name(
                stations,
                station_id,
            )
        )

        print(
            f"{index}. "
            f"{station_name} "
            f"[{station_id}]"
        )

    while True:
        raw_choice = input(
            "Nummer auswählen: "
        ).strip()

        try:
            choice = int(
                raw_choice
            )
        except ValueError:
            print(
                "Bitte eine Zahl eingeben."
            )
            continue

        if (
            1
            <= choice
            <= len(matches)
        ):
            return matches[
                choice - 1
            ]

        print(
            "Ungültige Auswahl."
        )


def make_service_key(
    edge: dict[str, Any],
) -> str:
    route_id = normalize_text(
        edge.get("route_id")
    )

    direction_id = normalize_text(
        edge.get("direction_id")
    )

    return (
        f"{route_id}"
        f"::{direction_id}"
    )


def find_best_route(
    graph: dict[
        str,
        list[dict[str, Any]],
    ],
    start_station_id: str,
    target_station_id: str,
    initial_service: str,
) -> dict[str, int] | None:
    """
    Gewichteter Dijkstra-Router.

    Zustand:
    aktuelle Station
    + aktuell verwendete Linie/Richtung

    Kosten:
    echte Reisezeit
    + Umstiegszeit
    + Komfortstrafe
    """

    start_state = (
        start_station_id,
        initial_service,
    )

    # Reihenfolge:
    # 1. generalisierte Zeit
    # 2. Umstiege
    # 3. tatsächliche Zeit
    # 4. gefahrene Haltestellen
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
            return {
                "generalized_time_seconds": (
                    current_cost[0]
                ),
                "transfers": (
                    current_cost[1]
                ),
                "actual_time_seconds": (
                    current_cost[2]
                ),
                "ride_stops": (
                    current_cost[3]
                ),
            }

        for edge in graph.get(
            station_id,
            [],
        ):
            next_station_id = (
                normalize_text(
                    edge.get("to")
                )
            )

            if not next_station_id:
                continue

            edge_type = normalize_text(
                edge.get("edge_type")
            )

            transfer_increment = 0
            transfer_penalty = 0
            extra_transfer_time = 0
            ride_stop_increment = 0

            if edge_type == "transfer":
                edge_time = parse_seconds(
                    edge.get(
                        "travel_time_seconds"
                    ),
                    DEFAULT_TRANSFER_TIME_SECONDS,
                )

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
                edge_time = parse_seconds(
                    edge.get(
                        "travel_time_seconds"
                    ),
                    DEFAULT_RIDE_TIME_SECONDS,
                )

                next_service = (
                    make_service_key(
                        edge
                    )
                )

                ride_stop_increment = 1

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

                    transfer_penalty = (
                        TRANSFER_PENALTY_SECONDS
                    )

                    extra_transfer_time = (
                        SAME_STATION_TRANSFER_TIME_SECONDS
                    )

            added_actual_time = (
                edge_time
                + extra_transfer_time
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

            old_cost = (
                best_cost.get(
                    next_state
                )
            )

            if (
                old_cost is not None
                and old_cost <= new_cost
            ):
                continue

            best_cost[
                next_state
            ] = new_cost

            heapq.heappush(
                queue,
                (
                    new_cost,
                    next(tie_breaker),
                    next_state,
                ),
            )

    return None


def build_service_options(
    current_station_id: str,
    graph: dict[
        str,
        list[dict[str, Any]],
    ],
    station_moves: dict[
        str,
        dict[str, Any],
    ],
) -> list[dict[str, Any]]:
    """
    Erstellt:

    1. direkt erreichbare Linien
    2. Linien, die über einen expliziten Fußweg
       erreichbar sind
    """

    options: list[
        dict[str, Any]
    ] = []

    seen_options: set[
        tuple[str, str]
    ] = set()

    def add_services(
        boarding_station_id: str,
        transfer_edge: (
            dict[str, Any]
            | None
        ),
    ) -> None:
        station_entry = (
            station_moves.get(
                boarding_station_id
            )
        )

        if station_entry is None:
            return

        for service in station_entry.get(
            "services",
            [],
        ):
            service_key = normalize_text(
                service.get(
                    "service_key"
                )
            )

            dedupe_key = (
                boarding_station_id,
                service_key,
            )

            if (
                not service_key
                or dedupe_key
                in seen_options
            ):
                continue

            seen_options.add(
                dedupe_key
            )

            options.append(
                {
                    "boarding_station_id": (
                        boarding_station_id
                    ),
                    "transfer_edge": (
                        transfer_edge
                    ),
                    "service": service,
                }
            )

    # Linien direkt an der aktuellen Station.
    add_services(
        current_station_id,
        None,
    )

    # Linien an einer über Fußweg erreichbaren Station.
    for edge in graph.get(
        current_station_id,
        [],
    ):
        if (
            normalize_text(
                edge.get("edge_type")
            )
            != "transfer"
        ):
            continue

        transfer_target = (
            normalize_text(
                edge.get("to")
            )
        )

        if transfer_target:
            add_services(
                transfer_target,
                edge,
            )

    options.sort(
        key=lambda option: (
            natural_sort_key(
                option[
                    "service"
                ].get(
                    "route_short_name"
                )
                or option[
                    "service"
                ].get(
                    "route_id"
                )
            ),
            option[
                "boarding_station_id"
            ],
            normalize_text(
                option[
                    "service"
                ].get(
                    "direction_id"
                )
            ),
        )
    )

    return options


def show_service_options(
    options: list[dict[str, Any]],
    stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    print(
        "\nVerfügbare Linien und Richtungen:"
    )

    for index, option in enumerate(
        options,
        start=1,
    ):
        service = option[
            "service"
        ]

        line_name = (
            normalize_text(
                service.get(
                    "route_short_name"
                )
            )
            or normalize_text(
                service.get(
                    "route_id"
                )
            )
        )

        headsigns = service.get(
            "headsigns",
            [],
        )

        direction_text = (
            ", ".join(
                headsigns[:3]
            )
            or "ohne Zielangabe"
        )

        access_text = ""

        transfer_edge = (
            option.get(
                "transfer_edge"
            )
        )

        if transfer_edge is not None:
            boarding_name = (
                get_station_name(
                    stations,
                    option[
                        "boarding_station_id"
                    ],
                )
            )

            transfer_seconds = (
                parse_seconds(
                    transfer_edge.get(
                        "travel_time_seconds"
                    ),
                    DEFAULT_TRANSFER_TIME_SECONDS,
                )
            )

            access_text = (
                " | "
                f"{format_minutes(transfer_seconds)} "
                f"Fußweg zu {boarding_name}"
            )

        destinations = service.get(
            "destinations",
            [],
        )

        example_destinations = (
            ", ".join(
                get_station_name(
                    stations,
                    destination[
                        "station_id"
                    ],
                )
                for destination
                in destinations[:4]
            )
        )

        print(
            f"{index:>2}. "
            f"{line_name} "
            f"| Richtung: "
            f"{direction_text}"
            f"{access_text}"
        )

        if example_destinations:
            print(
                "    Ausstiege z. B.: "
                f"{example_destinations}"
            )


def choose_service_option(
    options: list[dict[str, Any]],
) -> dict[str, Any] | None:
    while True:
        raw_choice = input(
            "\nLinienoption wählen "
            "(Nummer, q = Ende): "
        ).strip()

        if raw_choice.casefold() == "q":
            return None

        try:
            choice = int(
                raw_choice
            )
        except ValueError:
            print(
                "Bitte eine gültige Nummer eingeben."
            )
            continue

        if (
            1
            <= choice
            <= len(options)
        ):
            return options[
                choice - 1
            ]

        print(
            "Diese Linienoption existiert nicht."
        )


def print_destinations(
    destinations: list[
        dict[str, Any]
    ],
    stations: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    print(
        "\nMögliche Ausstiegsstationen:"
    )

    for index, destination in enumerate(
        destinations,
        start=1,
    ):
        station_name = (
            get_station_name(
                stations,
                destination[
                    "station_id"
                ],
            )
        )

        travel_seconds = (
            parse_seconds(
                destination.get(
                    "travel_time_seconds"
                ),
                DEFAULT_RIDE_TIME_SECONDS,
            )
        )

        stop_count = destination.get(
            "stop_count",
            "?",
        )

        print(
            f"{index:>3}. "
            f"{station_name} "
            f"| {format_minutes(travel_seconds)} "
            f"| {stop_count} Halte"
        )


def choose_destination(
    service: dict[str, Any],
    stations: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any] | None:
    destinations = list(
        service.get(
            "destinations",
            [],
        )
    )

    while True:
        raw_input = input(
            "Ausstiegsstation eingeben "
            "(? = Liste, b = zurück): "
        ).strip()

        if raw_input.casefold() == "b":
            return None

        if raw_input == "?":
            print_destinations(
                destinations,
                stations,
            )
            continue

        if raw_input.isdigit():
            choice = int(
                raw_input
            )

            if (
                1
                <= choice
                <= len(destinations)
            ):
                return destinations[
                    choice - 1
                ]

        search = normalize_search_text(
            raw_input
        )

        exact_matches = [
            destination
            for destination
            in destinations
            if normalize_search_text(
                get_station_name(
                    stations,
                    destination[
                        "station_id"
                    ],
                )
            ) == search
        ]

        partial_matches = (
            exact_matches
            or [
                destination
                for destination
                in destinations
                if search
                in normalize_search_text(
                    get_station_name(
                        stations,
                        destination[
                            "station_id"
                        ],
                    )
                )
            ]
        )

        if len(partial_matches) == 1:
            return partial_matches[0]

        if len(partial_matches) > 1:
            print(
                "\nMehrere passende Ausstiege:"
            )

            for index, destination in enumerate(
                partial_matches,
                start=1,
            ):
                station_name = (
                    get_station_name(
                        stations,
                        destination[
                            "station_id"
                        ],
                    )
                )

                print(
                    f"{index}. "
                    f"{station_name} "
                    f"[{destination['station_id']}]"
                )

            selection = input(
                "Nummer auswählen: "
            ).strip()

            if (
                selection.isdigit()
                and 1
                <= int(selection)
                <= len(partial_matches)
            ):
                return partial_matches[
                    int(selection) - 1
                ]

            print(
                "Ungültige Auswahl."
            )
            continue

        print(
            f"{RATING_SYMBOLS['gray']} "
            "Nicht möglich: Diese Station liegt "
            "nicht auf der gewählten Fahrt."
        )


def classify_move(
    optimal_seconds: int,
    projected_seconds: (
        int
        | None
    ),
) -> dict[str, Any]:
    if projected_seconds is None:
        return {
            "rating": "red",
            "label": (
                "Ziel von dort derzeit "
                "nicht erreichbar"
            ),
            "extra_seconds": None,
            "extra_ratio": None,
        }

    extra_seconds = max(
        0,
        projected_seconds
        - optimal_seconds,
    )

    extra_ratio = (
        extra_seconds
        / optimal_seconds
        if optimal_seconds > 0
        else 0.0
    )

    if (
        extra_seconds <= 60
        or extra_ratio <= 0.05
    ):
        rating = "green"

        label = (
            "Optimal oder praktisch optimal"
        )

    elif (
        extra_seconds <= 180
        or extra_ratio <= 0.12
    ):
        rating = "yellow"

        label = "Fast optimal"

    elif (
        extra_seconds <= 480
        or extra_ratio <= 0.30
    ):
        rating = "orange"

        label = "Vernünftiger Umweg"

    else:
        rating = "red"

        label = "Großer Umweg"

    return {
        "rating": rating,
        "label": label,
        "extra_seconds": (
            extra_seconds
        ),
        "extra_ratio": (
            extra_ratio
        ),
    }


def evaluate_move(
    graph: dict[
        str,
        list[dict[str, Any]],
    ],
    current_station_id: str,
    target_station_id: str,
    current_service: str,
    option: dict[str, Any],
    destination: dict[str, Any],
) -> dict[str, Any]:
    baseline = find_best_route(
        graph,
        current_station_id,
        target_station_id,
        current_service,
    )

    if baseline is None:
        raise RuntimeError(
            "Vom aktuellen Standort wurde "
            "keine Zielroute gefunden."
        )

    service = option[
        "service"
    ]

    next_service = normalize_text(
        service.get(
            "service_key"
        )
    )

    transfer_edge = option.get(
        "transfer_edge"
    )

    ride_time = parse_seconds(
        destination.get(
            "travel_time_seconds"
        ),
        DEFAULT_RIDE_TIME_SECONDS,
    )

    move_actual_time = (
        ride_time
    )

    move_generalized_time = (
        ride_time
    )

    move_transfers = 0
    access_transfer_time = 0
    same_station_transfer_time = 0

    if transfer_edge is not None:
        access_transfer_time = (
            parse_seconds(
                transfer_edge.get(
                    "travel_time_seconds"
                ),
                DEFAULT_TRANSFER_TIME_SECONDS,
            )
        )

        move_actual_time += (
            access_transfer_time
        )

        move_generalized_time += (
            access_transfer_time
        )

        if current_service not in {
            START_SERVICE,
            WALK_SERVICE,
        }:
            move_transfers += 1

            move_generalized_time += (
                TRANSFER_PENALTY_SECONDS
            )

    elif (
        current_service
        not in {
            START_SERVICE,
            WALK_SERVICE,
        }
        and current_service
        != next_service
    ):
        move_transfers += 1

        same_station_transfer_time = (
            SAME_STATION_TRANSFER_TIME_SECONDS
        )

        move_actual_time += (
            same_station_transfer_time
        )

        move_generalized_time += (
            same_station_transfer_time
            + TRANSFER_PENALTY_SECONDS
        )

    next_station_id = (
        normalize_text(
            destination.get(
                "station_id"
            )
        )
    )

    if (
        next_station_id
        == target_station_id
    ):
        remaining_route = {
            "generalized_time_seconds": 0,
            "actual_time_seconds": 0,
            "transfers": 0,
            "ride_stops": 0,
        }

    else:
        remaining_route = (
            find_best_route(
                graph,
                next_station_id,
                target_station_id,
                next_service,
            )
        )

    if remaining_route is None:
        projected_generalized_time = (
            None
        )

        projected_actual_time = (
            None
        )

    else:
        projected_generalized_time = (
            move_generalized_time
            + remaining_route[
                "generalized_time_seconds"
            ]
        )

        projected_actual_time = (
            move_actual_time
            + remaining_route[
                "actual_time_seconds"
            ]
        )

    rating = classify_move(
        baseline[
            "generalized_time_seconds"
        ],
        projected_generalized_time,
    )

    return {
        "baseline": baseline,
        "remaining": remaining_route,
        "rating": rating,
        "next_station_id": (
            next_station_id
        ),
        "next_service": (
            next_service
        ),
        "ride_time_seconds": (
            ride_time
        ),
        "access_transfer_time_seconds": (
            access_transfer_time
        ),
        "same_station_transfer_time_seconds": (
            same_station_transfer_time
        ),
        "move_actual_time_seconds": (
            move_actual_time
        ),
        "move_generalized_time_seconds": (
            move_generalized_time
        ),
        "move_transfers": (
            move_transfers
        ),
        "projected_actual_time_seconds": (
            projected_actual_time
        ),
        "projected_generalized_time_seconds": (
            projected_generalized_time
        ),
    }


def print_move_feedback(
    stations: dict[
        str,
        dict[str, Any],
    ],
    option: dict[str, Any],
    evaluation: dict[str, Any],
) -> None:
    service = option[
        "service"
    ]

    line_name = (
        normalize_text(
            service.get(
                "route_short_name"
            )
        )
        or normalize_text(
            service.get(
                "route_id"
            )
        )
    )

    destination_name = (
        get_station_name(
            stations,
            evaluation[
                "next_station_id"
            ],
        )
    )

    rating = evaluation[
        "rating"
    ]

    symbol = RATING_SYMBOLS[
        rating["rating"]
    ]

    print(
        "\n" + "=" * 72
    )

    print(
        f"{symbol} "
        f"{rating['label'].upper()}"
    )

    print("=" * 72)

    if (
        evaluation[
            "access_transfer_time_seconds"
        ] > 0
    ):
        boarding_name = (
            get_station_name(
                stations,
                option[
                    "boarding_station_id"
                ],
            )
        )

        print(
            "Fußweg zum Einstieg: "
            f"{format_minutes(evaluation['access_transfer_time_seconds'])} "
            f"nach {boarding_name}"
        )

    if (
        evaluation[
            "same_station_transfer_time_seconds"
        ] > 0
    ):
        print(
            "Geschätzte Umstiegszeit: "
            f"{format_minutes(evaluation['same_station_transfer_time_seconds'])}"
        )

    print(
        f"Gewählte Fahrt: "
        f"{line_name} "
        f"→ {destination_name}"
    )

    print(
        "Zeit dieses Spielzugs: "
        f"{format_minutes(evaluation['move_actual_time_seconds'])}"
    )

    projected_actual_time = (
        evaluation[
            "projected_actual_time_seconds"
        ]
    )

    if (
        projected_actual_time
        is not None
    ):
        print(
            "Voraussichtliche Restlösung "
            "einschließlich dieses Zugs: "
            f"{format_minutes(projected_actual_time)}"
        )

    extra_seconds = rating[
        "extra_seconds"
    ]

    if extra_seconds is not None:
        print(
            "Abweichung vom aktuell besten Weg: "
            f"+{format_minutes(extra_seconds)}"
        )

    else:
        print(
            "Vom neuen Standort wurde keine "
            "weitere Zielroute gefunden."
        )

    print(
        "Der Zug bleibt gültig; "
        "das Spiel läuft weiter."
    )


def main() -> None:
    stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    graph = load_json(
        WEIGHTED_GRAPH_FILE
    )

    move_index = load_json(
        MOVE_INDEX_FILE
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

    if not isinstance(
        move_index,
        dict,
    ):
        raise ValueError(
            "travel_move_index.json ist ungültig."
        )

    station_moves = move_index.get(
        "station_moves",
        {},
    )

    print("=" * 72)
    print("SSBDLE TRAVEL-GAME TEST")
    print("=" * 72)

    print(
        f"Stationen geladen: "
        f"{len(stations):,}"
    )

    print(
        f"Stationen mit Spielzügen: "
        f"{len(station_moves):,}"
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

    initial_best = find_best_route(
        graph,
        start_station_id,
        target_station_id,
        START_SERVICE,
    )

    if initial_best is None:
        print(
            "\nZwischen Start und Ziel wurde "
            "keine Verbindung gefunden."
        )
        return

    print(
        "\nBeste Ausgangslösung:"
    )

    print(
        "- Geschätzte Reisezeit: "
        f"{format_minutes(initial_best['actual_time_seconds'])}"
    )

    print(
        f"- Umstiege: "
        f"{initial_best['transfers']}"
    )

    print(
        "- Interner Routing-Score: "
        f"{format_minutes(initial_best['generalized_time_seconds'])}"
    )

    current_station_id = (
        start_station_id
    )

    current_service = (
        START_SERVICE
    )

    total_actual_seconds = 0
    total_transfers = 0
    move_number = 0

    while (
        current_station_id
        != target_station_id
        and move_number
        < MAX_MOVES
    ):
        current_best = (
            find_best_route(
                graph,
                current_station_id,
                target_station_id,
                current_service,
            )
        )

        print(
            "\n" + "-" * 72
        )

        print(
            "Aktuelle Station: "
            f"{get_station_name(stations, current_station_id)}"
        )

        print(
            "Ziel: "
            f"{get_station_name(stations, target_station_id)}"
        )

        print(
            f"Spielzug: "
            f"{move_number + 1} "
            f"von {MAX_MOVES}"
        )

        if current_best is not None:
            print(
                "Beste verbleibende Reisezeit: "
                f"{format_minutes(current_best['actual_time_seconds'])}"
            )

        options = build_service_options(
            current_station_id,
            graph,
            station_moves,
        )

        if not options:
            print(
                "Keine weiteren Fahrtmöglichkeiten gefunden."
            )
            break

        show_service_options(
            options,
            stations,
        )

        option = choose_service_option(
            options
        )

        if option is None:
            print(
                "Spieltest beendet."
            )
            return

        destination = choose_destination(
            option["service"],
            stations,
        )

        if destination is None:
            continue

        evaluation = evaluate_move(
            graph=graph,
            current_station_id=(
                current_station_id
            ),
            target_station_id=(
                target_station_id
            ),
            current_service=(
                current_service
            ),
            option=option,
            destination=destination,
        )

        print_move_feedback(
            stations,
            option,
            evaluation,
        )

        current_station_id = (
            evaluation[
                "next_station_id"
            ]
        )

        current_service = (
            evaluation[
                "next_service"
            ]
        )

        total_actual_seconds += (
            evaluation[
                "move_actual_time_seconds"
            ]
        )

        total_transfers += (
            evaluation[
                "move_transfers"
            ]
        )

        move_number += 1

    print(
        "\n" + "=" * 72
    )

    if (
        current_station_id
        == target_station_id
    ):
        print(
            "🎉 ZIEL ERREICHT"
        )

        print("=" * 72)

        print(
            f"Benötigte Spielzüge: "
            f"{move_number}"
        )

        print(
            "Geschätzte eigene Reisezeit: "
            f"{format_minutes(total_actual_seconds)}"
        )

        print(
            "Beste Ausgangsreisezeit: "
            f"{format_minutes(initial_best['actual_time_seconds'])}"
        )

        print(
            f"Eigene Umstiege: "
            f"{total_transfers}"
        )

        difference = (
            total_actual_seconds
            - initial_best[
                "actual_time_seconds"
            ]
        )

        if difference > 0:
            print(
                "Zeitabweichung: "
                f"+{format_minutes(difference)}"
            )

        else:
            print(
                "Zeitabweichung: optimal"
            )

    else:
        print(
            "MAXIMALE SPIELZUGZAHL ERREICHT"
        )

        print("=" * 72)

        print(
            "Letzte Station: "
            f"{get_station_name(stations, current_station_id)}"
        )

        print(
            "Schlechte Züge beenden das Spiel nicht sofort. "
            "Das aktuelle Testlimit liegt bei zehn Zügen."
        )


if __name__ == "__main__":
    main()