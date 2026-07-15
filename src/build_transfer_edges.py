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

TRANSFERS_FILE = (
    GTFS_DIR
    / "transfers.txt"
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

OUTPUT_TRANSFERS_JSON = (
    PROJECT_ROOT
    / "output"
    / "travel_transfers.json"
)

OUTPUT_REVIEW_CSV = (
    PROJECT_ROOT
    / "output"
    / "travel_transfers_review.csv"
)


# Wird verwendet, wenn für einen stationsübergreifenden
# Transfer keine konkrete Mindestzeit angegeben ist.
DEFAULT_TRANSFER_TIME_SECONDS = 180


def normalize_text(value: Any) -> str:
    """
    Wandelt Werte sicher in Text um.

    Pandas-NaN wird als leerer Text behandelt.
    """

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


def load_stop_mapping() -> dict[str, str]:
    """
    Lädt die Zuordnung:

    konkrete GTFS-Stop-ID
    → logische Travel-Station
    """

    if not STOP_MAPPING_FILE.exists():
        raise FileNotFoundError(
            "travel_stop_mapping.csv wurde nicht gefunden:\n"
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


def load_transfers() -> pd.DataFrame:
    if not TRANSFERS_FILE.exists():
        raise FileNotFoundError(
            f"transfers.txt wurde nicht gefunden:\n"
            f"{TRANSFERS_FILE}"
        )

    transfers = pd.read_csv(
        TRANSFERS_FILE,
        dtype=str,
        low_memory=False,
    )

    required_columns = {
        "from_stop_id",
        "to_stop_id",
        "transfer_type",
        "min_transfer_time",
    }

    missing_columns = (
        required_columns
        - set(transfers.columns)
    )

    if missing_columns:
        raise ValueError(
            "In transfers.txt fehlen folgende Spalten: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    return transfers


def parse_seconds(
    value: Any,
) -> int | None:
    text = normalize_text(value)

    if not text:
        return None

    try:
        numeric_value = float(text)
    except ValueError:
        return None

    if numeric_value < 0:
        return None

    return int(
        round(numeric_value)
    )


def build_transfer_edges(
    transfers: pd.DataFrame,
    stop_mapping: dict[str, str],
    travel_stations: dict[str, Any],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[str, int],
]:
    """
    Fasst konkrete Plattform-Transfers zu Transfers
    zwischen logischen Travel-Stationen zusammen.

    transfer_type 3 bedeutet:
    Ein Transfer ist ausdrücklich nicht möglich.
    Solche Verbindungen werden ausgeschlossen.
    """

    grouped_transfers: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    statistics = {
        "input_rows": len(transfers),
        "unmapped_rows": 0,
        "forbidden_rows": 0,
        "self_transfer_rows": 0,
        "usable_rows": 0,
    }

    for row in transfers.itertuples(
        index=False
    ):
        from_stop_id = normalize_text(
            row.from_stop_id
        )

        to_stop_id = normalize_text(
            row.to_stop_id
        )

        transfer_type = (
            normalize_text(
                row.transfer_type
            )
            or "0"
        )

        minimum_time = parse_seconds(
            row.min_transfer_time
        )

        # GTFS transfer_type 3:
        # Transfer ausdrücklich nicht möglich.
        if transfer_type == "3":
            statistics[
                "forbidden_rows"
            ] += 1

            continue

        from_station_id = (
            stop_mapping.get(
                from_stop_id
            )
        )

        to_station_id = (
            stop_mapping.get(
                to_stop_id
            )
        )

        if (
            not from_station_id
            or not to_station_id
        ):
            statistics[
                "unmapped_rows"
            ] += 1

            continue

        if (
            from_station_id
            not in travel_stations
            or to_station_id
            not in travel_stations
        ):
            statistics[
                "unmapped_rows"
            ] += 1

            continue

        # Bahnsteigwechsel innerhalb derselben bereits
        # zusammengefassten Station müssen im Stationsgraphen
        # nicht als zusätzliche Kante auftauchen.
        if (
            from_station_id
            == to_station_id
        ):
            statistics[
                "self_transfer_rows"
            ] += 1

            continue

        statistics[
            "usable_rows"
        ] += 1

        transfer_key = (
            from_station_id,
            to_station_id,
        )

        if (
            transfer_key
            not in grouped_transfers
        ):
            grouped_transfers[
                transfer_key
            ] = {
                "from": from_station_id,
                "to": to_station_id,
                "transfer_types": set(),
                "explicit_times": [],
                "source_pairs": set(),
                "source_count": 0,
            }

        transfer_group = (
            grouped_transfers[
                transfer_key
            ]
        )

        transfer_group[
            "transfer_types"
        ].add(
            transfer_type
        )

        if minimum_time is not None:
            transfer_group[
                "explicit_times"
            ].append(
                minimum_time
            )

        transfer_group[
            "source_pairs"
        ].add(
            (
                from_stop_id,
                to_stop_id,
            )
        )

        transfer_group[
            "source_count"
        ] += 1

    transfer_graph: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    review_rows: list[
        dict[str, Any]
    ] = []

    for (
        from_station_id,
        to_station_id,
    ), transfer_group in sorted(
        grouped_transfers.items()
    ):
        explicit_times = (
            transfer_group[
                "explicit_times"
            ]
        )

        explicit_minimum_time = (
            min(explicit_times)
            if explicit_times
            else None
        )

        # Ein expliziter Wert über 0 wird verwendet.
        # Bei 0 oder fehlender Angabe setzen wir zunächst
        # einen konservativen Standardwert von 180 Sekunden.
        if (
            explicit_minimum_time
            is not None
            and explicit_minimum_time > 0
        ):
            routing_time_seconds = (
                explicit_minimum_time
            )

            time_source = (
                "gtfs_min_transfer_time"
            )
        else:
            routing_time_seconds = (
                DEFAULT_TRANSFER_TIME_SECONDS
            )

            time_source = (
                "default_transfer_time"
            )

        from_name = (
            travel_stations[
                from_station_id
            ].get(
                "name",
                from_station_id,
            )
        )

        to_name = (
            travel_stations[
                to_station_id
            ].get(
                "name",
                to_station_id,
            )
        )

        transfer_edge = {
            "to": to_station_id,
            "edge_type": "transfer",
            "transfer_types": sorted(
                transfer_group[
                    "transfer_types"
                ]
            ),
            "min_transfer_time_seconds": (
                explicit_minimum_time
            ),
            "routing_time_seconds": (
                routing_time_seconds
            ),
            "time_source": time_source,
            "source_count": (
                transfer_group[
                    "source_count"
                ]
            ),
        }

        transfer_graph[
            from_station_id
        ].append(
            transfer_edge
        )

        review_rows.append(
            {
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
                "transfer_types": (
                    " | ".join(
                        sorted(
                            transfer_group[
                                "transfer_types"
                            ]
                        )
                    )
                ),
                "gtfs_min_transfer_time_seconds": (
                    explicit_minimum_time
                ),
                "routing_time_seconds": (
                    routing_time_seconds
                ),
                "time_source": (
                    time_source
                ),
                "source_count": (
                    transfer_group[
                        "source_count"
                    ]
                ),
                "source_platform_pairs": len(
                    transfer_group[
                        "source_pairs"
                    ]
                ),
            }
        )

    for station_id in transfer_graph:
        transfer_graph[
            station_id
        ].sort(
            key=lambda edge: (
                edge[
                    "routing_time_seconds"
                ],
                edge["to"],
            )
        )

    return (
        dict(transfer_graph),
        review_rows,
        statistics,
    )


def save_results(
    transfer_graph: dict[str, Any],
    review_rows: list[dict[str, Any]],
) -> None:
    OUTPUT_TRANSFERS_JSON.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_TRANSFERS_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            transfer_graph,
            file,
            ensure_ascii=False,
            indent=2,
        )

    pd.DataFrame(
        review_rows
    ).to_csv(
        OUTPUT_REVIEW_CSV,
        index=False,
        encoding="utf-8-sig",
    )


def print_transfer_examples(
    transfer_graph: dict[str, Any],
    travel_stations: dict[str, Any],
) -> None:
    example_names = [
        "Hauptbahnhof (tief)",
        "Hauptbahnhof (oben)",
        "Vaihingen",
        "Marienplatz",
    ]

    print(
        "\nBeispiel-Transfers:"
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
            ) == station_name
        ]

        print(
            f"\n{station_name}:"
        )

        if not matching_ids:
            print(
                "- Station nicht gefunden"
            )
            continue

        station_id = (
            matching_ids[0]
        )

        outgoing_transfers = (
            transfer_graph.get(
                station_id,
                [],
            )
        )

        if not outgoing_transfers:
            print(
                "- keine stationsübergreifenden Transfers"
            )
            continue

        for edge in outgoing_transfers[:15]:
            target_name = (
                travel_stations.get(
                    edge["to"],
                    {},
                ).get(
                    "name",
                    edge["to"],
                )
            )

            minutes = (
                edge[
                    "routing_time_seconds"
                ]
                / 60
            )

            print(
                "- "
                f"→ {target_name} "
                f"| {minutes:.1f} Minuten "
                f"| {edge['time_source']}"
            )


def main() -> None:
    travel_stations = load_json(
        TRAVEL_STATIONS_FILE
    )

    stop_mapping = (
        load_stop_mapping()
    )

    transfers = load_transfers()

    (
        transfer_graph,
        review_rows,
        statistics,
    ) = build_transfer_edges(
        transfers,
        stop_mapping,
        travel_stations,
    )

    save_results(
        transfer_graph,
        review_rows,
    )

    print("=" * 72)
    print("TRAVEL-TRANSFERS ERFOLGREICH ERSTELLT")
    print("=" * 72)

    print(
        f"GTFS-Transferzeilen:             "
        f"{statistics['input_rows']:,}"
    )

    print(
        f"Nicht zuordenbare Zeilen:        "
        f"{statistics['unmapped_rows']:,}"
    )

    print(
        f"Verbotene Transfers:             "
        f"{statistics['forbidden_rows']:,}"
    )

    print(
        f"Interne Bahnsteigtransfers:      "
        f"{statistics['self_transfer_rows']:,}"
    )

    print(
        f"Nutzbare Transferzeilen:         "
        f"{statistics['usable_rows']:,}"
    )

    print(
        f"Logische Transferverbindungen:   "
        f"{len(review_rows):,}"
    )

    print(
        f"Stationen mit Transfers:         "
        f"{len(transfer_graph):,}"
    )

    print(
        "\nTransfer-Graph:\n"
        f"{OUTPUT_TRANSFERS_JSON}"
    )

    print(
        "\nKontroll-CSV:\n"
        f"{OUTPUT_REVIEW_CSV}"
    )

    print_transfer_examples(
        transfer_graph,
        travel_stations,
    )


if __name__ == "__main__":
    main()