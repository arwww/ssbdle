from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "output"
    / "stations_game.json"
)

OUTPUT_DIR = PROJECT_ROOT / "output" / "analysis"


def load_stations() -> list[dict]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Datei nicht gefunden:\n{INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        stations = json.load(file)

    if not isinstance(stations, list):
        raise ValueError(
            "stations_game.json muss eine Liste enthalten."
        )

    return stations


def build_dataframe(
    stations: list[dict],
) -> pd.DataFrame:
    rows = []

    for station in stations:
        modes = station.get("modes", [])
        lines = station.get("lines", [])

        rows.append(
            {
                "id": station.get("id", ""),
                "name": station.get("name", ""),
                "name_with_place": station.get(
                    "name_with_place",
                    "",
                ),
                "municipality": station.get(
                    "municipality",
                    "",
                ),
                "locality": station.get(
                    "locality",
                    "",
                ),
                "modes": "; ".join(modes),
                "lines": ", ".join(lines),
                "line_count": station.get(
                    "line_count",
                    len(lines),
                ),
                "has_bus": any(
                    "bus" in mode.casefold()
                    for mode in modes
                ),
                "has_rail": any(
                    rail_term in mode.casefold()
                    for mode in modes
                    for rail_term in [
                        "stadtbahn",
                        "s-bahn",
                        "r-bahn",
                        "regionalbahn",
                        "seilbahn",
                        "zahnradbahn",
                    ]
                ),
            }
        )

    dataframe = pd.DataFrame(rows)

    dataframe["line_count"] = (
        pd.to_numeric(
            dataframe["line_count"],
            errors="coerce",
        )
        .fillna(0)
        .astype(int)
    )

    return dataframe


def save_reports(
    dataframe: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Vollständige Kontrollliste
    dataframe.sort_values(
        [
            "municipality",
            "line_count",
            "name",
        ],
        ascending=[
            True,
            False,
            True,
        ],
    ).to_csv(
        OUTPUT_DIR / "all_candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Namen, die mehrfach im Spielpool vorkommen
    duplicate_mask = dataframe.duplicated(
        subset=["name"],
        keep=False,
    )

    dataframe.loc[duplicate_mask].sort_values(
        ["name", "municipality"]
    ).to_csv(
        OUTPUT_DIR / "duplicate_names.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Reine Busstationen mit höchstens zwei Linien
    weak_bus_stations = dataframe[
        (dataframe["has_bus"])
        & (~dataframe["has_rail"])
        & (dataframe["line_count"] <= 2)
    ]

    weak_bus_stations.sort_values(
        ["municipality", "name"]
    ).to_csv(
        OUTPUT_DIR / "bus_only_max_2_lines.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Alle Stationen ohne Bahnanschluss
    dataframe[
        ~dataframe["has_rail"]
    ].sort_values(
        [
            "municipality",
            "line_count",
            "name",
        ],
        ascending=[
            True,
            False,
            True,
        ],
    ).to_csv(
        OUTPUT_DIR / "without_rail.csv",
        index=False,
        encoding="utf-8-sig",
    )


def print_summary(
    dataframe: pd.DataFrame,
) -> None:
    print("=" * 60)
    print("ANALYSE DES SPIELPOOLS")
    print("=" * 60)

    print(
        f"Haltestellen insgesamt: "
        f"{len(dataframe):,}"
    )

    print(
        f"Mit Bahnverkehr: "
        f"{dataframe['has_rail'].sum():,}"
    )

    print(
        f"Ohne Bahnverkehr: "
        f"{(~dataframe['has_rail']).sum():,}"
    )

    print(
        f"Reine Busstationen mit höchstens 2 Linien: "
        f"{len(dataframe[
            (dataframe['has_bus'])
            & (~dataframe['has_rail'])
            & (dataframe['line_count'] <= 2)
        ]):,}"
    )

    duplicate_names = dataframe[
        dataframe.duplicated(
            subset=["name"],
            keep=False,
        )
    ]

    print(
        f"Zeilen mit mehrfach vorkommendem Namen: "
        f"{len(duplicate_names):,}"
    )

    print("\nVerteilung nach Linienzahl:")

    bins = pd.cut(
        dataframe["line_count"],
        bins=[
            -1,
            1,
            2,
            4,
            7,
            10,
            float("inf"),
        ],
        labels=[
            "0–1",
            "2",
            "3–4",
            "5–7",
            "8–10",
            "mehr als 10",
        ],
    )

    print(
        bins.value_counts()
        .sort_index()
        .to_string()
    )

    print("\nVerkehrsmittel-Kombinationen:")

    print(
        dataframe["modes"]
        .value_counts()
        .head(15)
        .to_string()
    )

    print("\nAnalysedateien:")

    for filename in [
        "all_candidates.csv",
        "duplicate_names.csv",
        "bus_only_max_2_lines.csv",
        "without_rail.csv",
    ]:
        print(
            OUTPUT_DIR / filename
        )


def main() -> None:
    stations = load_stations()
    dataframe = build_dataframe(stations)

    save_reports(dataframe)
    print_summary(dataframe)


if __name__ == "__main__":
    main()