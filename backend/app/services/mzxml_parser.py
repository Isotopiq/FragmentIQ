from __future__ import annotations

import base64
import struct
import zlib
from pathlib import Path
from typing import Any


def _decode_peaks(encoded: str, compression: str | None, precision: int, byte_order: str | None = None) -> list[tuple[float, float]]:
    """Decode mzXML <peaks> base64 into (m/z, intensity) pairs."""
    raw = base64.b64decode(encoded)
    if compression == "zlib":
        raw = zlib.decompress(raw)

    if precision == 32:
        base = "f"
        width = 4
    else:
        base = "d"
        width = 8

    endian = ">" if byte_order and byte_order.lower() in {"network", "big"} else "<"
    fmt = f"{endian}{base}"

    values = []
    for i in range(0, len(raw), width):
        chunk = raw[i : i + width]
        if len(chunk) < width:
            break
        values.append(struct.unpack(fmt, chunk)[0])

    pairs: list[tuple[float, float]] = []
    for i in range(0, len(values) - 1, 2):
        pairs.append((float(values[i]), float(values[i + 1])))
    return pairs


def _first_text(element: Any, *paths: str) -> str | None:
    for path in paths:
        child = element.find(path)
        if child is not None and child.text:
            return child.text
    return None


def _ms_level_mzml(spectrum: Any) -> int | None:
    for cv in spectrum.findall(".//{http://psi.hupo.org/ms/mzml}cvParam"):
        name = cv.get("name")
        if name and "ms level" in name.lower():
            value = cv.get("value")
            if value:
                try:
                    return int(value)
                except ValueError:
                    pass
    return None


def _precursor_mz_mzml(spectrum: Any) -> float | None:
    for cv in spectrum.findall(".//{http://psi.hupo.org/ms/mzml}cvParam"):
        name = cv.get("name")
        if name and name.lower() in {"selected ion m/z", "isolation target m/z", "precursor m/z"}:
            value = cv.get("value")
            if value:
                try:
                    return float(value)
                except ValueError:
                    pass
    return None


def _decode_mzml_array(spectrum: Any, array_type: str) -> list[float] | None:
    ns = "{http://psi.hupo.org/ms/mzml}"
    for bda in spectrum.findall(f".//{ns}binaryDataArray"):
        for cv in bda.findall(f"{ns}cvParam"):
            if cv.get("name") == array_type:
                binary = bda.find(f"{ns}binary")
                if binary is None or not binary.text:
                    return None
                raw = base64.b64decode(binary.text.strip())
                compression = None
                precision = 32
                for cv_param in bda.findall(f"{ns}cvParam"):
                    name = cv_param.get("name", "").lower()
                    if "zlib" in name or "compression" in name and "zlib" in name:
                        compression = "zlib"
                    if "64-bit" in name or "64" in name:
                        precision = 64
                if compression == "zlib":
                    raw = zlib.decompress(raw)
                fmt = "<f" if precision == 32 else "<d"
                width = 4 if precision == 32 else 8
                return [struct.unpack(fmt, raw[i : i + width])[0] for i in range(0, len(raw), width) if len(raw[i : i + width]) == width]
    return None


def _namespace(tag: str, ns: str | None) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


def _parse_mzxml(path: Path) -> list[dict[str, Any]]:
    import xml.etree.ElementTree as ET

    spectra: list[dict[str, Any]] = []
    tree = ET.parse(path)
    root = tree.getroot()
    ns = None
    if root.tag.startswith("{"):
        ns = root.tag.split("}", 1)[0][1:]
    for scan in root.iter(_namespace("scan", ns)):
        ms_level = scan.get("msLevel")
        if ms_level and int(ms_level) != 2:
            continue
        precursor_mz = None
        precursor = scan.find(_namespace("precursorMz", ns))
        if precursor is not None and precursor.text:
            try:
                precursor_mz = float(precursor.text)
            except ValueError:
                pass
        peaks = scan.find(_namespace("peaks", ns))
        if peaks is None or not peaks.text:
            continue
        compression = peaks.get("compressionType")
        precision = int(peaks.get("precision", "32"))
        byte_order = peaks.get("byteOrder")
        try:
            pairs = _decode_peaks(peaks.text.strip(), compression, precision, byte_order)
        except Exception:
            continue
        if not pairs:
            continue
        num = scan.get("num") or scan.get("id")
        rt_text = scan.get("retentionTime", "")
        rt = None
        if rt_text:
            try:
                rt = float(rt_text.replace("PT", "").replace("S", ""))
            except ValueError:
                pass
        spectra.append({
            "feature_id": str(num) if num else f"scan_{len(spectra)+1}",
            "precursor_mz": precursor_mz,
            "peaks": pairs,
            "retention_time": rt,
        })
    return spectra


def _parse_mzml(path: Path) -> list[dict[str, Any]]:
    import xml.etree.ElementTree as ET

    ns = "{http://psi.hupo.org/ms/mzml}"
    spectra: list[dict[str, Any]] = []
    tree = ET.parse(path)
    root = tree.getroot()
    for spectrum in root.iter(f"{ns}spectrum"):
        ms_level = _ms_level_mzml(spectrum)
        if ms_level != 2:
            continue
        mzs = _decode_mzml_array(spectrum, "m/z array")
        intensities = _decode_mzml_array(spectrum, "intensity array")
        if not mzs or not intensities or len(mzs) != len(intensities):
            continue
        precursor_mz = _precursor_mz_mzml(spectrum)
        scan_id = spectrum.get("id") or f"scan_{len(spectra)+1}"
        spectra.append({
            "feature_id": scan_id,
            "precursor_mz": precursor_mz,
            "peaks": list(zip(mzs, intensities)),
            "retention_time": None,
        })
    return spectra


def extract_msms_spectra(path: Path) -> list[dict[str, Any]]:
    """Extract MS/MS spectra from mzXML or mzML files."""
    suffix = path.suffix.lower()
    if suffix == ".mzxml":
        return _parse_mzxml(path)
    if suffix == ".mzml":
        return _parse_mzml(path)
    raise ValueError(f"Unsupported raw file format: {suffix}")


def _tolerant_load_spectra(path: Path) -> list[dict[str, Any]]:
    """Load spectra from MGF/MSP/mzXML/mzML without requiring matchms."""
    from app.services.spectral_search import _load_library_spectra as _load_mgf_msp

    suffix = path.suffix.lower()
    if suffix in {".mgf", ".msp"}:
        return _load_mgf_msp(path)
    if suffix in {".mzxml", ".mzml"}:
        return extract_msms_spectra(path)
    raise ValueError(f"Unsupported query spectrum format: {suffix}")
