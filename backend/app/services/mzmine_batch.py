from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


def _batch_xml_root() -> ET.Element:
    """Return a minimal MZmine batch XML root element."""
    return ET.Element("batch")


def _sub_element(parent: ET.Element, tag: str, text: str | None = None, attrib: dict[str, str] | None = None) -> ET.Element:
    el = ET.SubElement(parent, tag, attrib or {})
    if text is not None:
        el.text = text
    return el


def _file_name_param(parent: ET.Element, file_paths: list[Path]) -> None:
    """Append MZmine <parameter name=\"File names\"> with <file> children."""
    param = _sub_element(parent, "parameter", attrib={"name": "File names"})
    for path in file_paths:
        _sub_element(param, "file", text=str(path))


def generate_mzmine_batch(
    raw_files: list[Path],
    output_dir: Path,
    parameters: dict[str, Any],
) -> str:
    """
    Build a default MZmine batch XML for centroided mzML/mzXML feature detection.
    Uses conservative module names that MZmine 3/4 supports through batch XML.
    """
    if not raw_files:
        raise ValueError("At least one raw file is required for MZmine batch generation.")

    ion_mode = str(parameters.get("ion_mode", "positive")).lower()
    noise_level = float(parameters.get("mass_detection_noise", 1000))
    rt_tol = float(parameters.get("rt_tolerance_minutes", 0.2))
    mz_tol_ppm = float(parameters.get("mz_tolerance_ppm", 10))

    batch = _batch_xml_root()

    # 1. Raw data import
    import_step = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.io.import_rawdata_all.AllSpectralDataImportModule"})
    _file_name_param(import_step, raw_files)

    # 2. Mass detection
    mass_detect = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.dataprocessing.featdet_massdetection.MassDetectionModule"})
    _sub_element(mass_detect, "parameter", text="Centroid", attrib={"name": "Mass detector"})
    _sub_element(mass_detect, "parameter", text=str(noise_level), attrib={"name": "Noise level"})

    # 3. Chromatogram builder
    chrom_builder = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.dataprocessing.featdet_adapchromatogrambuilder.ADAPChromatogramBuilderModule"})
    _sub_element(chrom_builder, "parameter", text=f"{mz_tol_ppm} ppm", attrib={"name": "m/z tolerance"})
    _sub_element(chrom_builder, "parameter", text="0.08 min", attrib={"name": "Minimum RT time"})

    # 4. Deconvolution (local minimum)
    deconv = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.dataprocessing.featdet_deconvolution.DeconvolutionModule"})
    _sub_element(deconv, "parameter", text="Local minimum search", attrib={"name": "Algorithm"})

    # 5. Isotope grouping
    isotopes = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.dataprocessing.filter_isotopegrouper.IsotopeGrouperModule"})
    _sub_element(isotopes, "parameter", text="0.01 m/z", attrib={"name": "m/z tolerance"})
    _sub_element(isotopes, "parameter", text="10", attrib={"name": "Maximum charge"})
    _sub_element(isotopes, "parameter", text="false", attrib={"name": "Remove original peaklist"})

    # 6. Join aligner
    join_align = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.dataprocessing.align_join.JoinAlignerModule"})
    _sub_element(join_align, "parameter", text=f"{mz_tol_ppm} ppm", attrib={"name": "m/z tolerance"})
    _sub_element(join_align, "parameter", text=f"{rt_tol} min", attrib={"name": "RT tolerance"})

    # 7. CSV feature table export
    feature_csv = output_dir / "feature_table.csv"
    csv_export = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.io.export_features_csv.CSVFeatureListExportModule"})
    _sub_element(csv_export, "parameter", text=str(feature_csv), attrib={"name": "Filename"})

    # 8. MGF spectral export
    mgf_export = output_dir / "spectra.mgf"
    mgf_step = _sub_element(batch, "batchstep", attrib={"method": "io.github.mzmine.modules.io.export_spectral_db.SpectralDBExportModule"})
    _sub_element(mgf_step, "parameter", text=str(mgf_export), attrib={"name": "Filename"})

    ET.indent(batch, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(batch, encoding="unicode")


def substitute_batch_placeholders(
    batch_text: str,
    raw_files: list[Path],
    output_dir: Path,
    parameters: dict[str, Any],
) -> str:
    """
    Replace common placeholder tokens with concrete values.
    """
    if not raw_files:
        raise ValueError("At least one raw file is required for placeholder substitution.")

    def escape(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    file_list_xml = "".join(f"<file>{escape(str(p))}</file>" for p in raw_files)
    replacements = {
        "UPLOADS_SELECTED_AT_RUNTIME": file_list_xml,
        "{UPLOADS}": file_list_xml,
        "{OUTPUT_DIR}": escape(str(output_dir)),
        "{ION_MODE}": escape(str(parameters.get("ion_mode", "positive"))),
        "{MZ_TOLERANCE}": escape(str(parameters.get("mz_tolerance_ppm", 10))),
        "{RT_TOLERANCE}": escape(str(parameters.get("rt_tolerance_minutes", 0.2))),
    }
    result = batch_text
    for token, value in replacements.items():
        result = result.replace(token, value)

    # Replace empty file tags inside File names parameter if present
    pattern = re.compile(r'(<parameter name="File names">)\s*(</parameter>)', re.IGNORECASE)
    result = pattern.sub(lambda m: f'{m.group(1)}\n{file_list_xml}\n{m.group(2)}', result)
    return result


def get_mzmine_batch_for_workflow(workflow, raw_files: list[Path], run_dir: Path) -> Path:
    """
    If the workflow has no mzbatch_text, generate a default batch.
    Otherwise substitute placeholders in the user-supplied batch text.
    """
    from app.core.storage import safe_child

    output = safe_child(run_dir, "workflow.mzbatch")
    if workflow and workflow.mzbatch_text:
        text = substitute_batch_placeholders(workflow.mzbatch_text, raw_files, run_dir, workflow.parameters or {})
    else:
        params = workflow.parameters if workflow else {}
        text = generate_mzmine_batch(raw_files, run_dir, params)
    output.write_text(text, encoding="utf-8")
    return output
