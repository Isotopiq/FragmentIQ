from __future__ import annotations

from pathlib import Path
from typing import Any


class SiriusApiClient:
    """PySirius-based REST client for SIRIUS 6+. Falls back to CLI if PySirius is unavailable."""

    def __init__(
        self,
        sirius_path: str | None,
        username: str,
        password: str,
        url: str | None = None,
        accept_terms: bool = True,
    ) -> None:
        self.sirius_path = sirius_path
        self.username = username
        self.password = password
        self.url = url
        self.accept_terms = accept_terms
        self._api = None
        self._sdk = None

    def _import_pysirius(self) -> Any:
        try:
            import PySirius
            return PySirius
        except ImportError as exc:
            raise RuntimeError("PySirius is not installed. Install 'py-sirius-ms' via /system/packages/install.") from exc

    def __enter__(self) -> "SiriusApiClient":
        PySirius = self._import_pysirius()
        SiriusSDK = PySirius.SiriusSDK
        AccountCredentials = PySirius.AccountCredentials
        if self.url:
            self._api = SiriusSDK().attach_to_sirius(self.url)
        else:
            self._api = SiriusSDK().attach_or_start_sirius(sirius_path=self.sirius_path)
        self._sdk = PySirius
        self._api.account().login(self.accept_terms, AccountCredentials(username=self.username, password=self.password))
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._api and self._sdk:
            try:
                self._sdk.SiriusSDK().shutdown_sirius(self._api)
            except Exception:
                pass

    @property
    def api(self) -> Any:
        return self._api

    def import_input(
        self,
        project_id: str,
        input_paths: list[Path],
        input_type: str = "ms_run",
    ) -> Any:
        if not self._api:
            raise RuntimeError("SIRIUS client not connected")
        project_api = self._api.projects()
        project_api.create_project(project_id, force=True)
        job_api = self._api.jobs()
        for path in input_paths:
            if input_type == "ms_run":
                job_api.import_preprocessed_data_as_job(project_id, str(path))
            else:
                job_api.import_ms_run_data_as_job(project_id, str(path))
        return project_api.get_project(project_id)

    def create_custom_spectral_database(self, db_name: str, library_mgf: Path) -> Any:
        if not self._api:
            raise RuntimeError("SIRIUS client not connected")
        db = self._api.databases().create_database(name=db_name)
        self._api.databases().import_into_database(db.get("id"), str(library_mgf))
        return db

    def run_identification(
        self,
        project_id: str,
        include_custom_dbs: bool = True,
        enable_canopus: bool = True,
        enable_zodiac: bool = True,
    ) -> Any:
        if not self._api:
            raise RuntimeError("SIRIUS client not connected")
        jobs_api = self._api.jobs()
        job = jobs_api.start_job(
            project_id,
            {
                "formulaId": True,
                "structure": True,
                "canopus": enable_canopus,
                "zodiac": enable_zodiac,
            },
        )
        self._api.wait_for_job_completion(project_id, job.get("id"), timeout=settings.job_timeout_seconds)
        return job

    def get_annotations(self, project_id: str) -> list[dict[str, Any]]:
        if not self._api:
            raise RuntimeError("SIRIUS client not connected")
        features = self._api.features().get_aligned_features(project_id)
        rows: list[dict[str, Any]] = []
        for feature in features:
            fid = feature.get("id")
            top = self._api.features().get_aligned_feature_top_annotation(project_id, fid)
            rows.append({
                "feature_id": fid,
                "mz": feature.get("mz"),
                "rt": feature.get("rt"),
                "formula": top.get("formula") if top else None,
                "candidate_name": top.get("name") if top else None,
                "smiles": top.get("smiles") if top else None,
                "inchikey": top.get("inchikey") if top else None,
                "sirius_formula_score": top.get("formulaScore") if top else None,
                "sirius_structure_score": top.get("score") if top else None,
                "canopus_class": top.get("canopusClass") if top else None,
                "canopus_probability": top.get("canopusProbability") if top else None,
                "zodiac_score": top.get("zodiacScore") if top else None,
                "annotation_source": "sirius_api",
            })
        return rows


def test_sirius_connection(
    sirius_path: str | None,
    username: str,
    password: str,
    url: str | None = None,
    accept_terms: bool = True,
) -> dict[str, Any]:
    """Test SIRIUS credentials and return account info without side effects."""
    try:
        with SiriusApiClient(sirius_path, username, password, url, accept_terms) as client:
            account = client.api.account().get_account_info()
            return {"status": "ok", "account": account.to_dict() if hasattr(account, "to_dict") else str(account)}
    except RuntimeError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:
        return {"status": "error", "message": f"SIRIUS connection failed: {exc}"}


# Imported here to avoid circular dependency
from app.core.config import settings  # noqa: E402
