from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GTFS_DIR = (
    PROJECT_ROOT
    / "data"
    / "gtfs-vvs"
    / "realtime"
)


def read_gtfs(
    filename: str,
    *,
    usecols: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    path = GTFS_DIR / filename

    if not path.exists():
        raise FileNotFoundError(
            f"Datei wurde nicht gefunden: {path}"
        )

    return pd.read_csv(
        path,
        dtype=str,
        usecols=usecols,
        nrows=nrows,
        low_memory=False,
    )


def show_file_columns(filename: str) -> None:
    frame = read_gtfs(
        filename,
        nrows=3,
    )

    print("\n" + "=" * 70)
    print(filename)
    print("=" * 70)

    print("Spalten:")
    for column in frame.columns:
        print(f"- {column}")

    print("\nBeispiel:")
    print(
        frame.head(2).to_string(
            index=False
        )
    )


def analyze_routes() -> None:
    routes = read_gtfs(
        "routes.txt",
        usecols=[
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_type",
        ],
    )

    print("\n" + "=" * 70)
    print("LINIEN")
    print("=" * 70)

    print(
        f"Linien-Datensätze: {len(routes):,}"
    )

    print(
        "Eindeutige Liniennamen: "
        f"{routes['route_short_name'].nunique():,}"
    )

    print("\nVerkehrsmitteltypen:")
    print(
        routes["route_type"]
        .value_counts(dropna=False)
        .sort_index()
        .to_string()
    )

    interesting = routes[
        routes["route_short_name"]
        .fillna("")
        .str.match(
            r"^(U\d+|S\d+|10|20|42|44)$",
            case=False,
        )
    ]

    print("\nBeispiele relevanter Linien:")
    print(
        interesting[
            [
                "route_short_name",
                "route_long_name",
                "route_type",
            ]
        ]
        .drop_duplicates()
        .sort_values(
            "route_short_name"
        )
        .head(100)
        .to_string(index=False)
    )


def analyze_stops() -> None:
    stops = read_gtfs(
        "stops.txt",
        usecols=[
            "stop_id",
            "stop_name",
            "stop_lat",
            "stop_lon",
            "location_type",
            "parent_station",
        ],
    )

    print("\n" + "=" * 70)
    print("HALTESTELLEN")
    print("=" * 70)

    print(
        f"Stop-Datensätze: {len(stops):,}"
    )

    print(
        "Eindeutige Namen: "
        f"{stops['stop_name'].nunique():,}"
    )

    for term in [
        "Esslingen",
        "Marienplatz",
        "Vaihingen",
        "Hauptbahnhof",
    ]:
        matches = stops[
            stops["stop_name"]
            .fillna("")
            .str.contains(
                term,
                case=False,
                regex=False,
            )
        ]

        print(
            f"\nTreffer für „{term}“: "
            f"{len(matches):,}"
        )

        print(
            matches[
                [
                    "stop_id",
                    "stop_name",
                    "location_type",
                    "parent_station",
                ]
            ]
            .head(20)
            .to_string(index=False)
        )


def analyze_trips() -> None:
    trips = read_gtfs(
        "trips.txt",
        usecols=[
            "route_id",
            "trip_id",
            "trip_headsign",
            "direction_id",
        ],
    )

    print("\n" + "=" * 70)
    print("FAHRTEN")
    print("=" * 70)

    print(
        f"Fahrten insgesamt: {len(trips):,}"
    )

    print(
        "Verwendete Linien-IDs: "
        f"{trips['route_id'].nunique():,}"
    )

    print("\nHäufigste Fahrtziele:")
    print(
        trips["trip_headsign"]
        .value_counts()
        .head(20)
        .to_string()
    )


def analyze_stop_times_sample() -> None:
    stop_times = read_gtfs(
        "stop_times.txt",
        usecols=[
            "trip_id",
            "stop_id",
            "stop_sequence",
            "arrival_time",
            "departure_time",
        ],
        nrows=100_000,
    )

    print("\n" + "=" * 70)
    print("STOP TIMES – ERSTE 100.000 ZEILEN")
    print("=" * 70)

    print(
        f"Eingelesene Zeilen: {len(stop_times):,}"
    )

    print(
        "Enthaltene Fahrten: "
        f"{stop_times['trip_id'].nunique():,}"
    )

    print(
        "Enthaltene Haltepunkte: "
        f"{stop_times['stop_id'].nunique():,}"
    )

    example_trip_id = (
        stop_times["trip_id"]
        .value_counts()
        .index[0]
    )

    example_trip = stop_times[
        stop_times["trip_id"]
        == example_trip_id
    ].sort_values(
        "stop_sequence",
        key=lambda values: pd.to_numeric(
            values,
            errors="coerce",
        ),
    )

    print(
        f"\nBeispiel-Fahrt: {example_trip_id}"
    )

    print(
        example_trip.head(30).to_string(
            index=False
        )
    )


def main() -> None:
    print(
        "Untersuchtes GTFS-Verzeichnis:\n"
        f"{GTFS_DIR}"
    )

    required_files = [
        "routes.txt",
        "trips.txt",
        "stops.txt",
        "stop_times.txt",
    ]

    for filename in required_files:
        if not (
            GTFS_DIR / filename
        ).exists():
            raise FileNotFoundError(
                f"Pflichtdatei fehlt: {filename}"
            )

    for filename in [
        "routes.txt",
        "trips.txt",
        "stops.txt",
        "stop_times.txt",
        "transfers.txt",
    ]:
        show_file_columns(filename)

    analyze_routes()
    analyze_stops()
    analyze_trips()
    analyze_stop_times_sample()

    print(f"analyse done")


if __name__ == "__main__":
    main()