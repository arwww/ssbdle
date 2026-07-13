from __future__ import annotations

import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

GAME_INPUT = (
    PROJECT_ROOT
    / "output"
    / "stations_game.json"
)

ANSWERS_INPUT = (
    PROJECT_ROOT
    / "output"
    / "stations_answers.json"
)

WEB_DATA_DIR = (
    PROJECT_ROOT
    / "web"
    / "data"
)

STATIONS_OUTPUT = (
    WEB_DATA_DIR
    / "stations.json"
)

ANSWER_IDS_OUTPUT = (
    WEB_DATA_DIR
    / "answer_ids.json"
)


def normalize_text(value: Any) -> str:
    """
    Vereinheitlicht Texte für Vergleiche.

    Beispiel:
    Böblingen -> boblingen
    """

    text = str(value or "").strip().casefold()
    normalized = unicodedata.normalize("NFKD", text)

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def load_json(path: Path) -> list[dict[str, Any]]:
    """Lädt und prüft eine JSON-Liste."""

    if not path.exists():
        raise FileNotFoundError(
            f"Datei wurde nicht gefunden:\n{path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{path.name} muss eine JSON-Liste enthalten."
        )

    return data


def create_labels(
    stations: list[dict[str, Any]],
) -> dict[str, str]:
    """
    Erstellt eindeutige Bezeichnungen für das Suchfeld.

    Eindeutiger Name:
        Charlottenplatz

    Doppelter Name:
        Rathaus (Stuttgart)
        Rathaus (Esslingen am Neckar)
    """

    name_counts = Counter(
        normalize_text(station.get("name"))
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
            station.get("municipality", "")
        ).strip()

        locality = str(
            station.get("locality", "")
        ).strip()

        normalized_name = normalize_text(name)

        if name_counts[normalized_name] == 1:
            label = name
        else:
            label = f"{name} ({municipality})"

        labels[station_id] = label

    # Prüfen, ob selbst nach Ergänzung der Gemeinde
    # noch doppelte Labels vorhanden sind.
    label_counts = Counter(
        normalize_text(label)
        for label in labels.values()
    )

    for station in stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        label = labels[station_id]

        if label_counts[normalize_text(label)] <= 1:
            continue

        name = str(
            station.get("name", "")
        ).strip()

        municipality = str(
            station.get("municipality", "")
        ).strip()

        locality = str(
            station.get("locality", "")
        ).strip()

        if locality and normalize_text(locality) != normalize_text(
            municipality
        ):
            labels[station_id] = (
                f"{name} ({municipality}, {locality})"
            )
        else:
            labels[station_id] = (
                f"{name} ({municipality}, {station_id})"
            )

    return labels


def build_web_stations(
    stations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reduziert die Datensätze auf spielrelevante Felder."""

    labels = create_labels(stations)
    web_stations: list[dict[str, Any]] = []

    for station in stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        if not station_id:
            continue

        lines = station.get("lines", [])
        modes = station.get("modes", [])

        web_station = {
            "id": station_id,
            "name": station.get("name", ""),
            "label": labels[station_id],
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

        web_stations.append(web_station)

    web_stations.sort(
        key=lambda station: normalize_text(
            station["label"]
        )
    )

    return web_stations


def save_json(
    path: Path,
    data: Any,
) -> None:
    """Speichert JSON lesbar und mit Umlauten."""

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


def main() -> None:
    WEB_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    game_stations = load_json(GAME_INPUT)
    answer_stations = load_json(ANSWERS_INPUT)

    web_stations = build_web_stations(
        game_stations
    )

    game_ids = {
        station["id"]
        for station in web_stations
    }

    answer_ids = []

    for station in answer_stations:
        station_id = str(
            station.get("id", "")
        ).strip()

        if station_id not in game_ids:
            raise ValueError(
                "Eine Lösungsstation fehlt im Eingabepool:\n"
                f"{station.get('name')} – {station_id}"
            )

        answer_ids.append(station_id)

    # Doppelte IDs entfernen, Reihenfolge erhalten.
    answer_ids = list(
        dict.fromkeys(answer_ids)
    )

    save_json(
        STATIONS_OUTPUT,
        web_stations,
    )

    save_json(
        ANSWER_IDS_OUTPUT,
        answer_ids,
    )

    labels = [
        station["label"]
        for station in web_stations
    ]

    duplicate_labels = [
        label
        for label, count in Counter(
            normalize_text(label)
            for label in labels
        ).items()
        if count > 1
    ]

    print("=" * 60)
    print("WEB-DATEN ERFOLGREICH ERSTELLT")
    print("=" * 60)

    print(
        f"Stationen für das Suchfeld: "
        f"{len(web_stations):,}"
    )

    print(
        f"Mögliche Lösungen: "
        f"{len(answer_ids):,}"
    )

    print(
        f"Doppelte Suchbezeichnungen: "
        f"{len(duplicate_labels):,}"
    )

    print(
        f"\nStationsdaten:\n{STATIONS_OUTPUT}"
    )

    print(
        f"\nLösungs-IDs:\n{ANSWER_IDS_OUTPUT}"
    )

    if web_stations:
        print("\nBeispieldatensatz:")

        print(
            json.dumps(
                web_stations[0],
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()