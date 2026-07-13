from pathlib import Path

import geopandas as gpd
import pandas as pd


# Hauptordner des Projekts
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"

HALTESTELLEN_CSV = (
    DATA_DIR
    / "haltestellen-vvs"
    / "vvs_haltestelle_j26.csv"
)

LINIEN_CSV = (
    DATA_DIR
    / "liniendaten-vvs"
    / "vvs_linien_j26.csv"
)

HALTESTELLEN_SHP = (
    DATA_DIR
    / "haltestellen-vvs"
    / "Haltestellen.shp"
)

LINIEN_SHP = (
    DATA_DIR
    / "liniendaten-vvs"
    / "Liniennetz.shp"
)


def read_csv_flexible(path: Path) -> pd.DataFrame:
    """
    Liest eine CSV-Datei und probiert dabei mehrere
    typische Zeichenkodierungen aus.

    sep=None lässt Pandas das Trennzeichen erkennen.
    dtype=str verhindert, dass IDs versehentlich als
    Zahlen verändert werden.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Datei nicht gefunden:\n{path}"
        )

    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin1",
    ]

    errors = []

    for encoding in encodings:
        try:
            dataframe = pd.read_csv(
                path,
                sep=None,
                engine="python",
                encoding=encoding,
                dtype=str,
            )

            print(
                f"CSV erfolgreich gelesen: {path.name} "
                f"mit Encoding {encoding}"
            )

            return dataframe

        except Exception as error:
            errors.append(
                f"{encoding}: {type(error).__name__}: {error}"
            )

    error_text = "\n".join(errors)

    raise RuntimeError(
        f"CSV konnte nicht gelesen werden:\n{path}\n\n"
        f"Versuche:\n{error_text}"
    )


def inspect_dataframe(
    name: str,
    dataframe: pd.DataFrame,
) -> None:
    """
    Gibt die wichtigsten Informationen eines DataFrames
    im Terminal aus.
    """

    print("\n")
    print("=" * 80)
    print(name)
    print("=" * 80)

    print(f"Zeilen:  {len(dataframe):,}")
    print(f"Spalten: {len(dataframe.columns):,}")

    print("\nSpaltennamen:")

    for number, column in enumerate(
        dataframe.columns,
        start=1,
    ):
        print(f"{number:>2}. {column}")

    print("\nErste fünf Zeilen:")

    if dataframe.empty:
        print("Der Datensatz ist leer.")
    else:
        print(
            dataframe
            .head(5)
            .to_string(index=False)
        )

    print("\nBeispielwerte je Spalte:")

    for column in dataframe.columns:
        values = (
            dataframe[column]
            .dropna()
            .astype(str)
            .str.strip()
        )

        values = values[values != ""]

        examples = (
            values
            .drop_duplicates()
            .head(5)
            .tolist()
        )

        missing_count = (
            dataframe[column].isna().sum()
            + dataframe[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

        missing_percentage = (
            missing_count / len(dataframe) * 100
            if len(dataframe) > 0
            else 0
        )

        print(
            f"- {column}: "
            f"Beispiele={examples}, "
            f"leer≈{missing_percentage:.1f}%"
        )


def inspect_shapefile(
    name: str,
    path: Path,
) -> gpd.GeoDataFrame:
    """
    Liest ein Shapefile und zeigt Spalten,
    Geometrietyp und Koordinatensystem.
    """

    if not path.exists():
        raise FileNotFoundError(
            f"Shapefile nicht gefunden:\n{path}"
        )

    geodataframe = gpd.read_file(path)

    print("\n")
    print("=" * 80)
    print(name)
    print("=" * 80)

    print(f"Zeilen: {len(geodataframe):,}")
    print(f"Koordinatensystem: {geodataframe.crs}")

    geometry_types = (
        geodataframe.geometry
        .geom_type
        .value_counts(dropna=False)
        .to_dict()
    )

    print(f"Geometrietypen: {geometry_types}")

    print("\nSpaltennamen:")

    for number, column in enumerate(
        geodataframe.columns,
        start=1,
    ):
        print(f"{number:>2}. {column}")

    print("\nErste fünf Zeilen ohne vollständige Geometrie:")

    preview = geodataframe.copy()
    preview["geometry"] = preview.geometry.astype(str)
    preview = geodataframe.drop(
    columns="geometry",
    errors="ignore",
)

    print(
       preview
       .head(5)
       .to_string(index=False))
    
    return geodataframe


def save_preview(
    dataframe: pd.DataFrame,
    filename: str,
) -> None:
    """
    Speichert bis zu 100 Zeilen als leicht öffnbare CSV.
    """

    output_path = OUTPUT_DIR / filename

    dataframe.head(100).to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"Vorschau gespeichert: {output_path}")


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Projektordner: {PROJECT_ROOT}")

    # CSV-Dateien laden
    haltestellen = read_csv_flexible(
        HALTESTELLEN_CSV
    )

    linien = read_csv_flexible(
        LINIEN_CSV
    )

    # CSV-Dateien untersuchen
    inspect_dataframe(
        "HALTESTELLEN-CSV",
        haltestellen,
    )

    inspect_dataframe(
        "LINIEN-CSV",
        linien,
    )

    # CSV-Vorschauen speichern
    save_preview(
        haltestellen,
        "haltestellen_preview.csv",
    )

    save_preview(
        linien,
        "linien_preview.csv",
    )

    # Shapefiles laden
    haltestellen_geo = inspect_shapefile(
        "HALTESTELLEN-SHAPEFILE",
        HALTESTELLEN_SHP,
    )

    linien_geo = inspect_shapefile(
        "LINIEN-SHAPEFILE",
        LINIEN_SHP,
    )

    # Attributtabellen ohne Geometrie speichern
    save_preview(
        haltestellen_geo.drop(
            columns="geometry"
        ),
        "haltestellen_shapefile_attribute.csv",
    )

    save_preview(
        linien_geo.drop(
            columns="geometry"
        ),
        "linien_shapefile_attribute.csv",
    )

    print("\n")
    print("=" * 80)
    print("INSPEKTION ERFOLGREICH ABGESCHLOSSEN")
    print("=" * 80)

    print(
        "Die Vorschaudateien befinden sich im Ordner output."
    )


if __name__ == "__main__":
    main()