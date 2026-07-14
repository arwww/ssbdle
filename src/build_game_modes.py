from __future__ import annotations

import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Callable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "output"
    / "stations_all.json"
)

GAME_MODES_OUTPUT = (
    PROJECT_ROOT
    / "web"
    / "data"
    / "game_modes.json"
)


WEB_STATIONS_OUTPUT = (
    PROJECT_ROOT
    / "web"
    / "data"
    / "stations_game_modes.json"
)

REVIEW_OUTPUT = (
    PROJECT_ROOT
    / "output"
    / "game_modes_review.csv"
)


MODE_DEFINITIONS = {
    "global": {
        "name": "Gesamtes Netz",
        "description": (
            "Stuttgart, wichtige Umlandstationen sowie "
            "alle Stadtbahn- und S-Bahn-Stationen."
        ),
        "image": "./assets/modes/mode-global.png",
    },
    "stuttgart": {
        "name": "Stuttgart",
        "description": (
            "Bus, Stadtbahn und Bahn innerhalb "
            "der Gemeinde Stuttgart."
        ),
        "image": "./assets/modes/mode-stuttgart.png",
    },
    "stadtbahn": {
        "name": "Stadtbahn",
        "description": (
            "Alle Haltestellen mit U-Linien, Stadtbahn, "
            "Zacke oder Seilbahn."
        ),
        "image": "./assets/modes/mode-stadtbahn.png",
    },
    "sbahn": {
        "name": "S-Bahn",
        "description": (
            "Alle S-Bahn-Stationen im vorhandenen "
            "VVS-Datensatz."
        ),
        "image": "./assets/modes/mode-sbahn.png",
    },
    "bus": {
        "name": "Bus",
        "description": (
            "Geeignete Tagesbus-Haltestellen in Stuttgart "
            "und ausgewählten Städten im Umland."
        ),
        "image": "./assets/modes/mode-bus.png",
    },
    "esslingen": {
        "name": "Esslingen",
        "description": (
            "Bahnstationen und größere Bushaltestellen "
            "in Esslingen am Neckar."
        ),
        "image": "./assets/modes/mode-esslingen.png",
    },
    "boeblingen": {
        "name": "Böblingen & Sindelfingen",
        "description": (
            "Bahnstationen und größere Bushaltestellen "
            "in Böblingen und Sindelfingen."
        ),
        "image": "./assets/modes/mode-boeblingen.png",
    },
}


SUPPORTED_MUNICIPALITIES = {
    "stuttgart",
    "esslingen am neckar",
    "boblingen",
    "sindelfingen",
    "fellbach",
    "filderstadt",
    "leinfelden-echterdingen",
    "leonberg",
    "ludwigsburg",
    "waiblingen",
}


SURROUNDING_MUNICIPALITIES = (
    SUPPORTED_MUNICIPALITIES
    - {"stuttgart"}
)


RAIL_MODES = {
    "stadtbahn",
    "s-bahn",
    "r-bahn",
    "regionalbahn",
    "zahnradbahn",
    "seilbahn",
}


STADTBAHN_RELATED_MODES = {
    "stadtbahn",
    "zahnradbahn",
    "seilbahn",
}


WEAK_MODES = {
    "nachtbus",
    "ruftaxi",
    "sev-bus",
}


IMPORTANT_KEYWORDS = {
    "hauptbahnhof",
    "bahnhof",
    "zob",
    "zentrum",
    "rathaus",
    "universitat",
    "flughafen",
    "messe",
    "stadmitte",
    "stadtmitte",
}


REGIONAL_RAIL_PREFIXES = (
    "rb",
    "re",
    "ire",
    "mex",
    "ic",
    "ice",
)


def normalize_text(value: Any) -> str:
    """
    Vereinheitlicht Text für Vergleiche.

    Beispiele:
    Böblingen -> boblingen
    Universität -> universitat
    """

    text = str(value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def load_stations() -> list[dict[str, Any]]:
    """Lädt alle zuvor aufbereiteten VVS-Stationen."""

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            "stations_all.json wurde nicht gefunden.\n"
            f"Erwarteter Pfad:\n{INPUT_FILE}\n\n"
            "Führe zuerst build_stations.py aus."
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        stations = json.load(file)

    if not isinstance(stations, list):
        raise ValueError(
            "stations_all.json muss eine JSON-Liste enthalten."
        )

    return stations


def get_modes(
    station: dict[str, Any],
) -> set[str]:
    """Gibt die normalisierten Verkehrsmittel zurück."""

    return {
        normalize_text(mode)
        for mode in station.get("modes", [])
        if normalize_text(mode)
    }


def get_lines(
    station: dict[str, Any],
) -> list[str]:
    """Gibt die normalisierten Linien zurück."""

    return [
        normalize_text(line)
        for line in station.get("lines", [])
        if normalize_text(line)
    ]


def is_night_line(line: str) -> bool:
    """
    Erkennt typische Nachtlinien wie N1, N5 oder N10.
    """

    return (
        line.startswith("n")
        and len(line) > 1
        and line[1:].isdigit()
    )


def is_replacement_line(line: str) -> bool:
    """Erkennt Schienenersatzverkehr."""

    return line.startswith("sev")


def is_u_line_name(line: str) -> bool:
    """
    Erkennt U-Linien einschließlich Varianten wie U1E.
    """

    return (
        line.startswith("u")
        and any(
            character.isdigit()
            for character in line[1:]
        )
    )


def is_sbahn_line_name(line: str) -> bool:
    """
    Erkennt echte S-Bahn-Linien wie S1, S2 oder S60.
    """

    return (
        line.startswith("s")
        and len(line) > 1
        and line[1:].isdigit()
    )


def is_regional_rail_line(line: str) -> bool:
    """
    Erkennt typische Regional- und Fernbahnbezeichnungen.
    """

    return line.startswith(
        REGIONAL_RAIL_PREFIXES
    )


def has_u_line(
    station: dict[str, Any],
) -> bool:
    """Prüft, ob mindestens eine U-Linie hält."""

    return any(
        is_u_line_name(line)
        for line in get_lines(station)
    )


def has_sbahn(
    station: dict[str, Any],
) -> bool:
    """
    Prüft S-Bahn sowohl über Verkehrsmittel
    als auch über Liniennamen.
    """

    if "s-bahn" in get_modes(station):
        return True

    return any(
        is_sbahn_line_name(line)
        for line in get_lines(station)
    )


def has_stadtbahn_related_mode(
    station: dict[str, Any],
) -> bool:
    """
    Schließt Stadtbahn, Zahnradbahn und Seilbahn ein.
    """

    return bool(
        get_modes(station)
        & STADTBAHN_RELATED_MODES
    )


def has_any_rail(
    station: dict[str, Any],
) -> bool:
    """Prüft, ob irgendein Bahnverkehrsmittel vorhanden ist."""

    return bool(
        get_modes(station)
        & RAIL_MODES
    )


def has_regular_bus(
    station: dict[str, Any],
) -> bool:
    """
    Reiner Nachtbus zählt nicht als normaler Bus.
    """

    return "bus" in get_modes(station)


def is_weak_mode_only(
    station: dict[str, Any],
) -> bool:
    """
    Entfernt Stationen, die ausschließlich über
    Nachtbus, Ruftaxi oder SEV verfügen.
    """

    modes = get_modes(station)

    return (
        bool(modes)
        and modes.issubset(WEAK_MODES)
    )


def is_special_non_bus_line(
    station: dict[str, Any],
    line: str,
) -> bool:
    """
    Verhindert, dass Zacke oder Seilbahn bei Stationen
    mit zusätzlichem Busanschluss als Buslinie zählen.

    Linie 10 = Zahnradbahn
    Linie 20 = Seilbahn
    """

    modes = get_modes(station)

    if (
        "zahnradbahn" in modes
        and line in {"10", "10e"}
    ):
        return True

    if (
        "seilbahn" in modes
        and line in {"20", "20e"}
    ):
        return True

    return False


def is_day_bus_line(
    station: dict[str, Any],
    line: str,
) -> bool:
    """
    Erkennt möglichst plausibel eine normale Tagesbuslinie.
    """

    if not line:
        return False

    if is_night_line(line):
        return False

    if is_replacement_line(line):
        return False

    if is_u_line_name(line):
        return False

    if is_sbahn_line_name(line):
        return False

    if is_regional_rail_line(line):
        return False

    if is_special_non_bus_line(
        station,
        line,
    ):
        return False

    return True


def get_day_bus_lines(
    station: dict[str, Any],
) -> set[str]:
    """
    Gibt die normalen Buslinien einer Station zurück.
    """

    if not has_regular_bus(station):
        return set()

    return {
        line
        for line in get_lines(station)
        if is_day_bus_line(
            station,
            line,
        )
    }


def count_day_bus_lines(
    station: dict[str, Any],
) -> int:
    """Zählt normale Tagesbuslinien."""

    return len(
        get_day_bus_lines(station)
    )


def count_relevant_lines(
    station: dict[str, Any],
) -> int:
    """
    Zählt alle Linien außer Nachtlinien und SEV.
    """

    relevant_lines = {
        line
        for line in get_lines(station)
        if not is_night_line(line)
        and not is_replacement_line(line)
    }

    return len(relevant_lines)


def contains_important_keyword(
    station: dict[str, Any],
) -> bool:
    """
    Erkennt Namen wie Bahnhof, ZOB oder Rathaus.
    """

    searchable_text = normalize_text(
        " ".join(
            [
                str(
                    station.get(
                        "name",
                        "",
                    )
                ),
                str(
                    station.get(
                        "name_with_place",
                        "",
                    )
                ),
            ]
        )
    )

    return any(
        keyword in searchable_text
        for keyword in IMPORTANT_KEYWORDS
    )


def station_is_valid(
    station: dict[str, Any],
) -> bool:
    """Prüft die wichtigsten Pflichtfelder."""

    station_id = str(
        station.get("id", "")
    ).strip()

    name = str(
        station.get("name", "")
    ).strip()

    latitude = station.get("latitude")
    longitude = station.get("longitude")

    return bool(
        station_id
        and name
        and latitude is not None
        and longitude is not None
    )


# ============================================================
# Auswahlregeln je Spielmodus
# Jede Funktion gibt einen Aufnahmegrund oder None zurück.
# ============================================================


def global_reason(
    station: dict[str, Any],
) -> str | None:
    municipality = normalize_text(
        station.get("municipality")
    )

    day_bus_count = count_day_bus_lines(
        station
    )

    # Diese Haltestellen müssen unabhängig vom Ort enthalten sein.
    if has_u_line(station):
        return "global_u_line"

    if has_stadtbahn_related_mode(station):
        return "global_stadtbahn_related"

    if has_sbahn(station):
        return "global_sbahn"

    if municipality == "stuttgart":
        if is_weak_mode_only(station):
            return None

        if has_any_rail(station):
            return "global_stuttgart_rail"
        
        

        if day_bus_count >= 3:
            return "global_stuttgart_bus"

        if (
            contains_important_keyword(station)
            and day_bus_count >= 2
        ):
            return "global_stuttgart_keyword"

        return None

    if municipality not in SURROUNDING_MUNICIPALITIES:
        return None

    if has_any_rail(station):
        return "global_surrounding_rail"

    if day_bus_count >= 4:
        return "global_surrounding_bus"

    if (
        contains_important_keyword(station)
        and day_bus_count >= 2
    ):
        return "global_surrounding_keyword"

    return None


def stuttgart_reason(
    station: dict[str, Any],
) -> str | None:
    municipality = normalize_text(
        station.get("municipality")
    )

    if municipality != "stuttgart":
        return None

    if is_weak_mode_only(station):
        return None

    if has_any_rail(station):
        return "stuttgart_rail"

    if count_day_bus_lines(station) >= 1:
        return "stuttgart_bus"

    if contains_important_keyword(station):
        return "stuttgart_keyword"

    return None


def stadtbahn_reason(
    station: dict[str, Any],
) -> str | None:
    modes = get_modes(station)

    if has_u_line(station):
        return "stadtbahn_u_line"

    if "stadtbahn" in modes:
        return "stadtbahn_mode"

    if "zahnradbahn" in modes:
        return "stadtbahn_zacke"

    if "seilbahn" in modes:
        return "stadtbahn_seilbahn"

    return None


def sbahn_reason(
    station: dict[str, Any],
) -> str | None:
    if has_sbahn(station):
        return "sbahn"

    return None


def bus_reason(
    station: dict[str, Any],
) -> str | None:
    municipality = normalize_text(
        station.get("municipality")
    )

    if municipality not in SUPPORTED_MUNICIPALITIES:
        return None

    if not has_regular_bus(station):
        return None

    if is_weak_mode_only(station):
        return None

    day_bus_count = count_day_bus_lines(
        station
    )

    if day_bus_count == 0:
        return None

    # In den Kerngebieten reichen drei Tagesbuslinien.
    # Im weiteren Umland müssen es mindestens vier sein.
    if municipality in {
        "stuttgart",
        "esslingen am neckar",
        "boblingen",
        "sindelfingen",
    }:
        minimum_lines = 3
    else:
        minimum_lines = 4

    if day_bus_count >= minimum_lines:
        return "bus_multiple_day_lines"

    # Größere Umsteigepunkte mit Bahnanschluss
    # bleiben ebenfalls im Busmodus enthalten.
    if (
        has_any_rail(station)
        and day_bus_count >= 2
    ):
        return "bus_rail_interchange"

    # Bedeutende Haltestellen wie Bahnhof, ZOB
    # oder Rathaus benötigen mindestens zwei Buslinien.
    if (
        contains_important_keyword(station)
        and day_bus_count >= 2
    ):
        return "bus_important_keyword"

    return None


def esslingen_reason(
    station: dict[str, Any],
) -> str | None:
    municipality = normalize_text(
        station.get("municipality")
    )

    if municipality != "esslingen am neckar":
        return None

    if is_weak_mode_only(station):
        return None

    # Alle Bahnstationen in Esslingen bleiben enthalten.
    if has_any_rail(station):
        return "esslingen_rail"

    day_bus_count = count_day_bus_lines(
        station
    )

    # Nur größere Bushaltestellen.
    if day_bus_count >= 3:
        return "esslingen_multiple_bus_lines"

    if (
        contains_important_keyword(station)
        and day_bus_count >= 2
    ):
        return "esslingen_keyword"

    return None


def boeblingen_reason(
    station: dict[str, Any],
) -> str | None:
    municipality = normalize_text(
        station.get("municipality")
    )

    if municipality not in {
        "boblingen",
        "sindelfingen",
    }:
        return None

    if is_weak_mode_only(station):
        return None

    # Alle Bahnstationen in Böblingen und
    # Sindelfingen bleiben enthalten.
    if has_any_rail(station):
        return "boeblingen_rail"

    day_bus_count = count_day_bus_lines(
        station
    )

    # Nur größere Bushaltestellen.
    if day_bus_count >= 3:
        return "boeblingen_multiple_bus_lines"

    if (
        contains_important_keyword(station)
        and day_bus_count >= 2
    ):
        return "boeblingen_keyword"

    return None

MODE_REASON_FUNCTIONS: dict[
    str,
    Callable[
        [dict[str, Any]],
        str | None,
    ],
] = {
    "global": global_reason,
    "stuttgart": stuttgart_reason,
    "stadtbahn": stadtbahn_reason,
    "sbahn": sbahn_reason,
    "bus": bus_reason,
    "esslingen": esslingen_reason,
    "boeblingen": boeblingen_reason,
}


def build_mode_selections(
    stations: list[dict[str, Any]],
) -> tuple[
    dict[str, list[str]],
    dict[str, dict[str, str]],
]:
    """
    Erzeugt je Modus eine ID-Liste und speichert
    zusätzlich den Aufnahmegrund.
    """

    mode_ids = {
        mode_id: []
        for mode_id in MODE_DEFINITIONS
    }

    mode_reasons = {
        mode_id: {}
        for mode_id in MODE_DEFINITIONS
    }

    sorted_stations = sorted(
        stations,
        key=lambda station: (
            normalize_text(
                station.get(
                    "municipality"
                )
            ),
            normalize_text(
                station.get(
                    "name"
                )
            ),
        ),
    )

    for station in sorted_stations:
        if not station_is_valid(station):
            continue

        station_id = str(
            station["id"]
        ).strip()

        for (
            mode_id,
            reason_function,
        ) in MODE_REASON_FUNCTIONS.items():
            reason = reason_function(
                station
            )

            if reason is None:
                continue

            if (
                station_id
                in mode_reasons[mode_id]
            ):
                continue

            mode_ids[
                mode_id
            ].append(
                station_id
            )

            mode_reasons[
                mode_id
            ][
                station_id
            ] = reason

    return mode_ids, mode_reasons


def create_unique_labels(
    stations: list[dict[str, Any]],
) -> dict[str, str]:
    """
    Erzeugt eindeutige Namen für die Suchvorschläge.
    """

    name_counts = Counter(
        normalize_text(
            station.get("name")
        )
        for station in stations
    )

    labels: dict[str, str] = {}

    for station in stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        name = str(
            station.get("name", "")
        ).strip()

        municipality = str(
            station.get(
                "municipality",
                "",
            )
        ).strip()

        normalized_name = normalize_text(
            name
        )

        if (
            name_counts[
                normalized_name
            ] == 1
        ):
            label = name
        else:
            label = (
                f"{name} "
                f"({municipality})"
            )

        labels[station_id] = label

    label_counts = Counter(
        normalize_text(label)
        for label in labels.values()
    )

    for station in stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        current_label = labels[
            station_id
        ]

        if (
            label_counts[
                normalize_text(
                    current_label
                )
            ] <= 1
        ):
            continue

        name = str(
            station.get(
                "name",
                "",
            )
        ).strip()

        municipality = str(
            station.get(
                "municipality",
                "",
            )
        ).strip()

        locality = str(
            station.get(
                "locality",
                "",
            )
        ).strip()

        if (
            locality
            and normalize_text(locality)
            != normalize_text(
                municipality
            )
        ):
            labels[station_id] = (
                f"{name} "
                f"({municipality}, {locality})"
            )
        else:
            labels[station_id] = (
                f"{name} "
                f"({municipality}, {station_id})"
            )

    return labels


def build_web_stations(
    stations: list[dict[str, Any]],
    mode_ids: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """
    Erzeugt den Eingabepool aus allen Stationen,
    die in mindestens einem Spielmodus vorkommen.

    So ist garantiert, dass jede Lösung auch über
    die Suche gefunden werden kann.
    """

    selected_ids = {
        station_id
        for ids in mode_ids.values()
        for station_id in ids
    }

    selected_stations = [
        station
        for station in stations
        if str(
            station.get("id", "")
        ).strip() in selected_ids
    ]

    labels = create_unique_labels(
        selected_stations
    )

    web_stations = []

    for station in selected_stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        lines = list(
            dict.fromkeys(
                station.get(
                    "lines",
                    [],
                )
            )
        )

        modes = list(
            dict.fromkeys(
                station.get(
                    "modes",
                    [],
                )
            )
        )

        web_stations.append(
            {
                "id": station_id,
                "name": station.get(
                    "name",
                    "",
                ),
                "label": labels[
                    station_id
                ],
                "municipality": station.get(
                    "municipality",
                    "",
                ),
                "locality": station.get(
                    "locality",
                    "",
                ),
                "tariff_zones": station.get(
                    "tariff_zones",
                    [],
                ),
                "modes": modes,
                "lines": lines,
                "line_count": len(lines),
                "longitude": station.get(
                    "longitude"
                ),
                "latitude": station.get(
                    "latitude"
                ),
            }
        )

    web_stations.sort(
        key=lambda station: normalize_text(
            station["label"]
        )
    )

    return web_stations


def build_game_modes_output(
    mode_ids: dict[str, list[str]],
) -> dict[str, Any]:
    """Erzeugt die spätere JSON-Struktur für JavaScript."""

    output: dict[str, Any] = {}

    for (
        mode_id,
        definition,
    ) in MODE_DEFINITIONS.items():
        output[mode_id] = {
            **definition,
            "enabled": True,
            "answer_count": len(
                mode_ids[mode_id]
            ),
            "answer_ids": mode_ids[
                mode_id
            ],
        }

    return output


def build_review_rows(
    stations: list[dict[str, Any]],
    mode_ids: dict[str, list[str]],
    mode_reasons: dict[
        str,
        dict[str, str],
    ],
) -> list[dict[str, Any]]:
    """Erzeugt eine Kontrolltabelle für Excel."""

    station_by_id = {
        str(
            station.get("id", "")
        ).strip(): station
        for station in stations
    }

    review_rows = []

    for (
        mode_id,
        station_ids,
    ) in mode_ids.items():
        for station_id in station_ids:
            station = station_by_id.get(
                station_id,
                {},
            )

            review_rows.append(
                {
                    "mode_id": mode_id,
                    "mode_name": (
                        MODE_DEFINITIONS[
                            mode_id
                        ]["name"]
                    ),
                    "selection_reason": (
                        mode_reasons[
                            mode_id
                        ][
                            station_id
                        ]
                    ),
                    "station_id": station_id,
                    "name": station.get(
                        "name",
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
                    "modes": "; ".join(
                        station.get(
                            "modes",
                            [],
                        )
                    ),
                    "lines": ", ".join(
                        station.get(
                            "lines",
                            [],
                        )
                    ),
                    "day_bus_line_count": (
                        count_day_bus_lines(
                            station
                        )
                    ),
                    "relevant_line_count": (
                        count_relevant_lines(
                            station
                        )
                    ),
                    "has_u_line": has_u_line(
                        station
                    ),
                    "has_sbahn": has_sbahn(
                        station
                    ),
                    "important_keyword": (
                        contains_important_keyword(
                            station
                        )
                    ),
                }
            )

    return review_rows


def save_json(
    path: Path,
    data: Any,
) -> None:
    """Speichert eine JSON-Datei mit Umlauten."""

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


def save_results(
    game_modes_output: dict[str, Any],
    web_stations: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
) -> None:
    """Speichert alle Ergebnisse."""

    save_json(
        GAME_MODES_OUTPUT,
        game_modes_output,
    )

    save_json(
        WEB_STATIONS_OUTPUT,
        web_stations,
    )

    REVIEW_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pd.DataFrame(
        review_rows
    ).to_csv(
        REVIEW_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )


def validate_results(
    mode_ids: dict[str, list[str]],
    web_stations: list[dict[str, Any]],
) -> None:
    """
    Prüft, dass jede Lösung im Eingabepool vorkommt.
    """

    web_station_ids = {
        station["id"]
        for station in web_stations
    }

    for (
        mode_id,
        station_ids,
    ) in mode_ids.items():
        if not station_ids:
            raise ValueError(
                f"Der Spielmodus {mode_id} ist leer."
            )

        missing_ids = [
            station_id
            for station_id in station_ids
            if station_id
            not in web_station_ids
        ]

        if missing_ids:
            raise ValueError(
                f"Im Modus {mode_id} fehlen "
                f"{len(missing_ids)} IDs im Suchpool."
            )


def print_summary(
    stations: list[dict[str, Any]],
    mode_ids: dict[str, list[str]],
    web_stations: list[dict[str, Any]],
) -> None:
    """Gibt eine verständliche Zusammenfassung aus."""

    print("=" * 72)
    print("SPIELMODI ERFOLGREICH AKTUALISIERT")
    print("=" * 72)

    print(
        "Haltestellen in stations_all.json: "
        f"{len(stations):,}"
    )

    print(
        "Haltestellen im neuen Suchpool:    "
        f"{len(web_stations):,}"
    )

    print("\nLösungen je Spielmodus:")

    for (
        mode_id,
        station_ids,
    ) in mode_ids.items():
        mode_name = (
            MODE_DEFINITIONS[
                mode_id
            ]["name"]
        )

        print(
            f"- {mode_name:<28} "
            f"{len(station_ids):>5,}"
        )

    print(
        "\nSpielmodi-JSON:\n"
        f"{GAME_MODES_OUTPUT}"
    )

    print(
        "\nNeuer Suchpool:\n"
        f"{WEB_STATIONS_OUTPUT}"
    )

    print(
        "\nKontroll-CSV:\n"
        f"{REVIEW_OUTPUT}"
    )


def main() -> None:
    stations = load_stations()

    mode_ids, mode_reasons = (
        build_mode_selections(
            stations
        )
    )

    web_stations = build_web_stations(
        stations,
        mode_ids,
    )

    game_modes_output = (
        build_game_modes_output(
            mode_ids
        )
    )

    review_rows = build_review_rows(
        stations,
        mode_ids,
        mode_reasons,
    )

    validate_results(
        mode_ids,
        web_stations,
    )

    save_results(
        game_modes_output,
        web_stations,
        review_rows,
    )

    print_summary(
        stations,
        mode_ids,
        web_stations,
    )


if __name__ == "__main__":
    main()