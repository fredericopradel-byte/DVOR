#!/usr/bin/env python3
"""Build the IV-PLANNER offline AIXM package from an official AIXM 5.1 XML.

The package deliberately contains complementary files:
  * a deterministic ZIP with the untouched source XML, divided into parts
    below GitHub's 25 MiB browser-upload limit;
  * a compact JSON index for fast, offline application queries.

Only Python's standard library and lxml are required.  The source XML is
streamed so the builder does not need to load the complete AIXM file in RAM.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from lxml import etree


GML = "http://www.opengis.net/gml/3.2"
XLINK = "http://www.w3.org/1999/xlink"
GML_ID = f"{{{GML}}}id"
XLINK_HREF = f"{{{XLINK}}}href"
MAX_PART_BYTES = 20 * 1024 * 1024

INDEXED_TYPES = {
    "AirportHeliport": "aerodromes",
    "Runway": "runways",
    "RunwayDirection": "runwayDirections",
    "RunwayCentrelinePoint": "runwayPoints",
    "Navaid": "navaids",
    "VOR": "navaidEquipment",
    "DME": "navaidEquipment",
    "NDB": "navaidEquipment",
    "Localizer": "navaidEquipment",
    "Glidepath": "navaidEquipment",
    "MarkerBeacon": "navaidEquipment",
    "VisualGlideSlopeIndicator": "visualGlideSlopeIndicators",
    "DesignatedPoint": "designatedPoints",
    "Airspace": "airspaces",
    "Route": "routes",
    "RouteSegment": "routeSegments",
    "StandardInstrumentDeparture": "procedures",
    "StandardInstrumentArrival": "procedures",
    "InstrumentApproachProcedure": "procedures",
}


def local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def clean_ref(value: str | None) -> str | None:
    if not value:
        return None
    return value.removeprefix("urn:uuid:").removeprefix("uuid.")


def feature_id(feature: etree._Element) -> str | None:
    for element in feature.iter():
        if local_name(element) == "identifier" and element.text:
            return element.text.strip()
    return clean_ref(feature.get(GML_ID))


def first_element(root: etree._Element, name: str) -> etree._Element | None:
    for element in root.iter():
        if local_name(element) == name:
            return element
    return None


def first_text(root: etree._Element, name: str) -> str | None:
    element = first_element(root, name)
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def texts(root: etree._Element, name: str) -> list[str]:
    values = []
    for element in root.iter():
        if local_name(element) == name and element.text and element.text.strip():
            values.append(element.text.strip())
    return values


def ref(root: etree._Element, name: str) -> str | None:
    element = first_element(root, name)
    return clean_ref(element.get(XLINK_HREF)) if element is not None else None


def refs(root: etree._Element, name: str) -> list[str]:
    result = []
    for element in root.iter():
        if local_name(element) == name:
            value = clean_ref(element.get(XLINK_HREF))
            if value and value not in result:
                result.append(value)
    return result


def number(value: str | None):
    if value is None:
        return None
    try:
        parsed = float(value)
        return int(parsed) if parsed.is_integer() else parsed
    except ValueError:
        return value


def measure(root: etree._Element, name: str):
    element = first_element(root, name)
    if element is None or element.text is None:
        return None
    result = {"value": number(element.text.strip())}
    if element.get("uom"):
        result["uom"] = element.get("uom")
    return result


def position(root: etree._Element):
    value = first_text(root, "pos")
    if not value:
        return None
    parts = value.split()
    if len(parts) < 2:
        return None
    try:
        return {"lat": float(parts[0]), "lon": float(parts[1])}
    except ValueError:
        return None


def base_record(feature: etree._Element, kind: str) -> dict:
    return {
        "id": feature_id(feature),
        "featureType": kind,
        "validFrom": first_text(feature, "beginPosition"),
        "interpretation": first_text(feature, "interpretation"),
    }


def compact(record: dict) -> dict:
    return {key: value for key, value in record.items() if value is not None and value != []}


def index_feature(feature: etree._Element, kind: str) -> dict:
    record = base_record(feature, kind)

    if kind == "AirportHeliport":
        record.update({
            "designator": first_text(feature, "designator"),
            "name": first_text(feature, "name"),
            "type": first_text(feature, "type"),
            "privateUse": first_text(feature, "privateUse"),
            "position": position(feature),
            "fieldElevation": measure(feature, "fieldElevation"),
            "magneticVariation": number(first_text(feature, "magneticVariation")),
            "magneticVariationDate": first_text(feature, "dateMagneticVariation"),
            "servedCities": texts(feature, "name")[1:],
            "ciad": first_text(feature, "attr_ciad"),
            "state": first_text(feature, "utc"),
        })
    elif kind == "Runway":
        record.update({
            "designator": first_text(feature, "designator"),
            "type": first_text(feature, "type"),
            "nominalLength": measure(feature, "nominalLength"),
            "nominalWidth": measure(feature, "nominalWidth"),
            "surfaceComposition": first_text(feature, "composition"),
            "airportId": ref(feature, "associatedAirportHeliport"),
        })
    elif kind == "RunwayDirection":
        record.update({
            "designator": first_text(feature, "designator"),
            "trueBearing": number(first_text(feature, "trueBearing")),
            "magneticBearing": number(first_text(feature, "magneticBearing")),
            "runwayId": ref(feature, "usedRunway"),
        })
    elif kind == "RunwayCentrelinePoint":
        record.update({
            "designator": first_text(feature, "designator"),
            "role": first_text(feature, "role"),
            "position": position(feature),
            "elevation": measure(feature, "elevation"),
            "runwayId": ref(feature, "onRunway"),
        })
    elif kind == "Navaid":
        record.update({
            "designator": first_text(feature, "designator"),
            "name": first_text(feature, "name"),
            "type": first_text(feature, "type"),
            "purpose": first_text(feature, "purpose"),
            "flightChecked": first_text(feature, "flightChecked"),
            "signalPerformance": first_text(feature, "signalPerformance"),
            "position": position(feature),
            "elevation": measure(feature, "elevation"),
            "equipmentIds": refs(feature, "theNavaidEquipment"),
            "runwayDirectionId": ref(feature, "runwayDirection"),
            "airportId": ref(feature, "servedAirport"),
        })
    elif kind in {"VOR", "DME", "NDB", "Localizer", "Glidepath", "MarkerBeacon"}:
        record.update({
            "equipmentType": kind,
            "designator": first_text(feature, "designator"),
            "name": first_text(feature, "name"),
            "position": position(feature),
            "elevation": measure(feature, "elevation"),
            "frequency": measure(feature, "frequency"),
            "channel": first_text(feature, "channel"),
            "magneticVariation": number(first_text(feature, "magneticVariation")),
            "magneticVariationDate": first_text(feature, "dateMagneticVariation"),
            "operationalStatus": first_text(feature, "operationalStatus"),
            "flightChecked": first_text(feature, "flightChecked"),
        })
    elif kind == "VisualGlideSlopeIndicator":
        record.update({
            "type": first_text(feature, "type"),
            "side": first_text(feature, "position"),
            "numberOfBoxes": number(first_text(feature, "numberBox")),
            "slopeAngle": number(first_text(feature, "slopeAngle")),
            "minimumEyeHeightOverThreshold": measure(feature, "minimumEyeHeightOverThreshold"),
            "runwayDirectionId": ref(feature, "runwayDirection"),
        })
    elif kind == "DesignatedPoint":
        record.update({
            "designator": first_text(feature, "designator"),
            "name": first_text(feature, "name"),
            "type": first_text(feature, "type"),
            "position": position(feature),
        })
    elif kind == "Airspace":
        record.update({
            "designator": first_text(feature, "designator"),
            "name": first_text(feature, "name"),
            "type": first_text(feature, "type"),
            "class": first_text(feature, "class"),
            "upperLimit": measure(feature, "upperLimit"),
            "upperLimitReference": first_text(feature, "upperLimitReference"),
            "lowerLimit": measure(feature, "lowerLimit"),
            "lowerLimitReference": first_text(feature, "lowerLimitReference"),
        })
    elif kind == "Route":
        record.update({
            "name": first_text(feature, "name"),
            "type": first_text(feature, "type"),
            "flightRule": first_text(feature, "flightRule"),
            "designatorPrefix": first_text(feature, "designatorPrefix"),
            "designatorSecondLetter": first_text(feature, "designatorSecondLetter"),
            "designatorNumber": first_text(feature, "designatorNumber"),
        })
    elif kind == "RouteSegment":
        record.update({
            "routeId": ref(feature, "routeFormed"),
            "level": first_text(feature, "level"),
            "upperLimit": measure(feature, "upperLimit"),
            "upperLimitReference": first_text(feature, "upperLimitReference"),
            "lowerLimit": measure(feature, "lowerLimit"),
            "lowerLimitReference": first_text(feature, "lowerLimitReference"),
            "trueTrack": number(first_text(feature, "trueTrack")),
            "magneticTrack": number(first_text(feature, "magneticTrack")),
            "reverseTrueTrack": number(first_text(feature, "reverseTrueTrack")),
            "reverseMagneticTrack": number(first_text(feature, "reverseMagneticTrack")),
            "length": measure(feature, "length"),
            "minimumEnrouteAltitude": measure(feature, "minimumEnrouteAltitude"),
            "navigationType": first_text(feature, "navigationType"),
            "requiredNavigationPerformance": number(first_text(feature, "requiredNavigationPerformance")),
        })
        endpoint_refs = []
        for container_name in ("start", "end"):
            container = first_element(feature, container_name)
            endpoint = None
            if container is not None:
                for element in container.iter():
                    value = clean_ref(element.get(XLINK_HREF))
                    if value:
                        endpoint = {"featureType": local_name(element), "id": value}
                        break
            endpoint_refs.append(endpoint)
        record["start"] = endpoint_refs[0]
        record["end"] = endpoint_refs[1]
    elif kind in {"StandardInstrumentDeparture", "StandardInstrumentArrival", "InstrumentApproachProcedure"}:
        record.update({
            "procedureType": kind,
            "name": first_text(feature, "name"),
            "designator": first_text(feature, "designator"),
            "designCriteria": first_text(feature, "designCriteria"),
            "rnav": first_text(feature, "RNAV"),
            "airportId": ref(feature, "airportHeliport"),
            "runwayDirectionIds": refs(feature, "runwayDirection"),
        })

    return compact(record)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_source(source: Path):
    feature_counts = collections.Counter()
    indexed = {name: [] for name in sorted(set(INDEXED_TYPES.values()))}
    effective_date = ""

    context = etree.iterparse(str(source), events=("end",), huge_tree=True, recover=False)
    for _, element in context:
        parent = element.getparent()
        if parent is None or local_name(parent) != "hasMember":
            continue

        kind = local_name(element)
        feature_counts[kind] += 1
        starts = texts(element, "beginPosition")
        for timestamp in starts:
            candidate = timestamp[:10]
            if candidate > effective_date:
                effective_date = candidate

        bucket = INDEXED_TYPES.get(kind)
        if bucket:
            indexed[bucket].append(index_feature(element, kind))

        element.clear()
        while element.getprevious() is not None:
            del parent[0]

    if not feature_counts:
        raise ValueError("Nenhum membro AIXM foi encontrado no XML.")
    if not effective_date:
        raise ValueError("Não foi possível determinar a vigência do AIXM.")
    return feature_counts, indexed, effective_date


def add_relationships(indexed: dict):
    airports = {item["id"]: item for item in indexed["aerodromes"] if item.get("id")}
    runways = {item["id"]: item for item in indexed["runways"] if item.get("id")}
    directions = {item["id"]: item for item in indexed["runwayDirections"] if item.get("id")}

    def airport_summary(airport_id):
        airport = airports.get(airport_id)
        if not airport:
            return None
        return compact({"id": airport_id, "designator": airport.get("designator"), "name": airport.get("name")})

    for runway in indexed["runways"]:
        runway["airport"] = airport_summary(runway.get("airportId"))
    for direction in indexed["runwayDirections"]:
        runway = runways.get(direction.get("runwayId"))
        if runway:
            direction["runwayDesignator"] = runway.get("designator")
            direction["airport"] = airport_summary(runway.get("airportId"))
    for point in indexed["runwayPoints"]:
        runway = runways.get(point.get("runwayId"))
        if runway:
            point["runwayDesignator"] = runway.get("designator")
            point["airport"] = airport_summary(runway.get("airportId"))
    for indicator in indexed["visualGlideSlopeIndicators"]:
        direction = directions.get(indicator.get("runwayDirectionId"))
        if direction:
            indicator["runwayDirectionDesignator"] = direction.get("designator")
            runway = runways.get(direction.get("runwayId"))
            if runway:
                indicator["runwayDesignator"] = runway.get("designator")
                indicator["airport"] = airport_summary(runway.get("airportId"))
    for navaid in indexed["navaids"]:
        navaid["airport"] = airport_summary(navaid.get("airportId"))
    for procedure in indexed["procedures"]:
        procedure["airport"] = airport_summary(procedure.get("airportId"))


def write_source_zip(source: Path, output: Path, effective_date: str):
    parsed_date = date.fromisoformat(effective_date)
    stamp = (max(parsed_date.year, 1980), parsed_date.month, parsed_date.day, 0, 0, 0)
    info = zipfile.ZipInfo(source.name, date_time=stamp)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        with source.open("rb") as input_stream, archive.open(info, "w", force_zip64=True) as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def split_archive(archive: Path, output_directory: Path) -> list[dict]:
    parts = []
    with archive.open("rb") as source:
        part_number = 1
        while chunk := source.read(MAX_PART_BYTES):
            part_path = output_directory / f"aixm-brasil-5.1.zip.part{part_number:02d}"
            part_path.write_bytes(chunk)
            parts.append({
                "fileName": part_path.name,
                "size": part_path.stat().st_size,
                "sha256": sha256(part_path),
            })
            part_number += 1
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_xml", type=Path)
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()

    source = args.source_xml.resolve()
    output_directory = args.output_directory.resolve()
    if not source.is_file():
        parser.error(f"arquivo inexistente: {source}")
    output_directory.mkdir(parents=True, exist_ok=True)

    source_hash = sha256(source)
    feature_counts, indexed, effective_date = parse_source(source)
    add_relationships(indexed)
    version = f"AIXM-BR-{effective_date}-r2"

    with tempfile.TemporaryDirectory(prefix="ivplanner-aixm-") as temporary_directory:
        archive_path = Path(temporary_directory) / "aixm-brasil-5.1.zip"
        write_source_zip(source, archive_path, effective_date)
        archive_size = archive_path.stat().st_size
        archive_hash = sha256(archive_path)
        archive_parts = split_archive(archive_path, output_directory)

    index = {
        "schema": "ivplanner-aixm-core-v1",
        "version": version,
        "effectiveDate": effective_date,
        "generatedAt": f"{effective_date}T00:00:00Z",
        "source": "DECEA AISWEB — AIXM 5.1",
        "sourceFile": source.name,
        "sourceSha256": source_hash,
        "sourceArchive": {
            "fileName": "aixm-brasil-5.1.zip",
            "format": "binary-parts",
            "joinOrder": [part["fileName"] for part in archive_parts],
            "size": archive_size,
            "sha256": archive_hash,
            "parts": archive_parts,
        },
        "featureCount": sum(feature_counts.values()),
        "featureTypes": dict(sorted(feature_counts.items())),
        "coverageNotice": "Índice operacional derivado do AIXM. O ZIP anexo preserva integralmente o XML oficial recebido.",
        "limitations": [
            "O arquivo recebido não contém registros VerticalStructure/obstáculos; a base OPEA permanece um pacote separado."
        ],
        **indexed,
    }
    index_path = output_directory / "aixm-core.json"
    with index_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(index, stream, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        stream.write("\n")

    result = {
        "version": version,
        "effectiveDate": effective_date,
        "source": {"path": str(source), "size": source.stat().st_size, "sha256": source_hash},
        "files": [
            {"path": str(index_path), "size": index_path.stat().st_size, "sha256": sha256(index_path)},
            *[
                {
                    "path": str(output_directory / part["fileName"]),
                    "size": part["size"],
                    "sha256": part["sha256"],
                }
                for part in archive_parts
            ],
        ],
        "featureCount": sum(feature_counts.values()),
        "indexedCounts": {name: len(items) for name, items in indexed.items()},
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
