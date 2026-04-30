"""
Runtime procedure retrieval from canonical TSS (Test Support System).

This module loads procedures from `LTV_ERRORS.json` at runtime, never persists
procedure content to disk, and keeps only an in-memory cache with a TTL.

The example payload stores LTV procedures in an `error_procedures` array, where
each entry contains an error `code`, a human-readable `description`, and a
single `procedures` array of numbered text blocks. This loader normalizes that
shape into `Procedure`/`ProcedureStep` objects and indexes them by code,
description, and derived aliases.
"""
import hashlib
import hmac
import json
import logging
import os
import threading
import time
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from procedures import Procedure, ProcedureStep

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in text).strip("_")


def _split_numbered_steps(text: str) -> List[str]:
    """Split a single string of concatenated numbered steps into separate steps."""
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return []

    matches = list(re.finditer(r"(?=(?:^|\s)(\d+)\.\s)", cleaned))
    if not matches:
        return [cleaned]

    steps: List[str] = []
    for index, match in enumerate(matches):
        start = match.start(1)
        end = matches[index + 1].start(1) if index + 1 < len(matches) else len(cleaned)
        chunk = cleaned[start:end].strip()
        if chunk:
            steps.append(chunk)
    return steps


class ProcedureStore:
    def __init__(self,
                 tss_url: Optional[str] = None,
                 hmac_secret: Optional[str] = None,
                 cache_ttl: int = 300,
                 audit_log_path: Optional[str] = None,
                 source_filename: str = "LTV_ERRORS.json"):
        self.tss_url = tss_url
        self.hmac_secret = hmac_secret.encode() if hmac_secret else None
        self.cache_ttl = cache_ttl
        self.source_filename = source_filename
        self._catalog_cache: Dict[str, Procedure] = {}
        self._error_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._catalog_loaded_at: float = 0.0
        self._cache_lock = threading.Lock()
        self.audit_log_path = audit_log_path

    def _audit(self, proc_id: str, requester: str, status: str, reason: Optional[str] = None):
        entry = {
            "ts": int(time.time()),
            "proc_id": proc_id,
            "requester": requester,
            "status": status,
            "reason": reason,
        }
        line = json.dumps(entry)
        logger.info(f"Procedure audit: {line}")
        if self.audit_log_path:
            try:
                with open(self.audit_log_path, "a", encoding="utf-8") as file_handle:
                    file_handle.write(line + "\n")
            except Exception as exc:
                logger.warning(f"Failed to write audit log: {exc}")

    def _catalog_is_valid(self) -> bool:
        return bool(self._catalog_cache) and (time.time() - self._catalog_loaded_at) < self.cache_ttl

    def _build_procedure(self, node: Dict[str, Any]) -> Optional[Procedure]:
        payload = node.get("procedure") if isinstance(node.get("procedure"), dict) else node
        if not isinstance(payload, dict):
            return None

        steps: List[ProcedureStep] = []
        raw_steps = payload.get("steps") or payload.get("procedures") or []

        # The example schema stores the step text as a single string inside the
        # procedures array. Split those into numbered step chunks first.
        expanded_step_nodes: List[Any] = []
        for raw_step in raw_steps if isinstance(raw_steps, list) else [raw_steps]:
            if isinstance(raw_step, str):
                expanded_step_nodes.extend(_split_numbered_steps(raw_step))
            else:
                expanded_step_nodes.append(raw_step)

        for index, step_node in enumerate(expanded_step_nodes, start=1):
            if isinstance(step_node, dict):
                try:
                    steps.append(
                        ProcedureStep(
                            number=int(step_node.get("number", index)),
                            action=str(step_node.get("action", step_node.get("text", ""))).strip(),
                            target=str(step_node.get("target", step_node.get("location", ""))).strip(),
                            wait_condition=step_node.get("wait_condition") or step_node.get("wait"),
                            notes=step_node.get("notes"),
                        )
                    )
                except Exception as exc:
                    logger.warning(f"Skipping malformed step in procedure payload: {exc}")
            else:
                step_text = str(step_node).strip()
                if not step_text:
                    continue
                # Extract the numeric prefix and preserve the rest as the action.
                match = re.match(r"^(\d+)\.\s*(.*)$", step_text)
                number = int(match.group(1)) if match else index
                action = match.group(2).strip() if match else step_text
                steps.append(ProcedureStep(number=number, action=action, target="LTV"))

        if not steps:
            return None

        code = str(payload.get("code") or payload.get("error_code") or payload.get("id") or "").strip()
        description = str(payload.get("description") or payload.get("name") or payload.get("title") or code or "").strip()
        mission_phase = str(payload.get("mission_phase") or payload.get("phase") or "repair").strip()
        name = description if description else code or "unknown"
        return Procedure(name=name, description=description, steps=steps, mission_phase=mission_phase)

    def _register_procedure(self, catalog: Dict[str, Procedure], procedure: Procedure, aliases: Iterable[Optional[str]]) -> None:
        for alias in aliases:
            if not alias:
                continue
            catalog[_normalize(alias)] = procedure

        # Also index by split tokens so queries like "bus connector" can match
        normalized_name = _normalize(procedure.name)
        if normalized_name:
            catalog[normalized_name] = procedure

    def _register_error_metadata(self, proc_id: str, metadata: Dict[str, Any]) -> None:
        normalized_id = _normalize(proc_id)
        self._error_metadata_cache[normalized_id] = metadata
        code = metadata.get("code")
        if code is not None:
            self._error_metadata_cache[_normalize(str(code))] = metadata
        description = metadata.get("description")
        if description:
            self._error_metadata_cache[_normalize(str(description))] = metadata

    def _extract_procedures(self, payload: Any) -> Dict[str, Procedure]:
        catalog: Dict[str, Procedure] = {}
        self._error_metadata_cache = {}

        def register_error_entry(node: Dict[str, Any]) -> None:
            procedure = self._build_procedure(node)
            if procedure is None:
                return

            code = node.get("code") or node.get("error_code") or node.get("id")
            description = node.get("description") or node.get("name") or node.get("title")
            aliases = [code, description, procedure.name]
            self._register_procedure(catalog, procedure, aliases)
            if code is not None:
                self._register_error_metadata(
                    str(code),
                    {
                        "code": str(code),
                        "description": str(description or procedure.name),
                        "needs_resolved": bool(node.get("needs_resolved", False)),
                        "procedure": procedure,
                        "raw": node,
                    },
                )

        def walk(node: Any, alias_hint: Optional[str] = None):
            if isinstance(node, list):
                for item in node:
                    walk(item, alias_hint=alias_hint)
                return

            if not isinstance(node, dict):
                return

            if "error_procedures" in node and isinstance(node["error_procedures"], list):
                for item in node["error_procedures"]:
                    if isinstance(item, dict):
                        register_error_entry(item)
                return

            if any(key in node for key in ("code", "description", "procedures", "steps")):
                procedure = self._build_procedure(node)
                if procedure is not None:
                    aliases = [alias_hint, node.get("id"), node.get("key"), node.get("code"), node.get("error_code"), node.get("procedure_id"), node.get("name"), node.get("title"), node.get("description")]
                    self._register_procedure(catalog, procedure, aliases)
                    if node.get("code") is not None:
                        self._register_error_metadata(
                            str(node.get("code")),
                            {
                                "code": str(node.get("code")),
                                "description": str(node.get("description") or node.get("name") or procedure.name),
                                "needs_resolved": bool(node.get("needs_resolved", False)),
                                "procedure": procedure,
                                "raw": node,
                            },
                        )
                    return

            for key, value in node.items():
                if isinstance(value, (dict, list)):
                    walk(value, alias_hint=key)

        walk(payload)
        return catalog

    def _fetch_source_payload(self) -> Optional[Any]:
        # Prefer the live telemetry snapshot if it already contains the file.
        try:
            from telemetry import get_current_telemetry

            snapshot = get_current_telemetry() or {}
            for key in (self.source_filename, self.source_filename.replace("ERRORS", "ERROS"), self.source_filename.replace("ERROS", "ERRORS")):
                if key in snapshot:
                    return snapshot[key]
        except Exception as exc:
            logger.debug(f"Telemetry snapshot unavailable for procedure source lookup: {exc}")

        base_url = self.tss_url or os.getenv("TELEMETRY_SERVER_BASE")
        if base_url:
            try:
                import requests

                candidates = [self.source_filename]
                if "ERRORS" in self.source_filename:
                    candidates.append(self.source_filename.replace("ERRORS", "ERROS"))
                if "ERROS" in self.source_filename:
                    candidates.append(self.source_filename.replace("ERROS", "ERRORS"))

                for candidate in candidates:
                    url = f"{base_url.rstrip('/')}/data/{candidate}"
                    try:
                        response = requests.get(url, timeout=5)
                        response.raise_for_status()
                        payload = response.json()

                        # If a signature is provided, verify it but do not require one yet.
                        signature = payload.get("signature") if isinstance(payload, dict) else None
                        procedure_payload = payload.get("procedures", payload) if isinstance(payload, dict) else payload
                        if self.hmac_secret and signature and isinstance(procedure_payload, (dict, list)):
                            computed = hmac.new(
                                self.hmac_secret,
                                json.dumps(procedure_payload, sort_keys=True).encode("utf-8"),
                                hashlib.sha256,
                            ).hexdigest()
                            if not hmac.compare_digest(computed, signature):
                                self._audit(candidate, "remote", "invalid_signature")
                                logger.warning("Procedure source signature mismatch")
                                continue

                        self._audit(candidate, "remote", "fetched_source")
                        return procedure_payload
                    except Exception as candidate_exc:
                        logger.debug(f"Failed to fetch candidate {candidate}: {candidate_exc}")
                        continue

                self._audit(self.source_filename, "remote", "fetch_error", reason="all_candidates_failed")
            except Exception as exc:
                logger.exception(f"Failed to fetch procedure source {self.source_filename}: {exc}")
                self._audit(self.source_filename, "remote", "fetch_error", reason=str(exc))
        # Development fallback: use the checked-in docs copy if runtime source is unavailable.
        local_candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", self.source_filename),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", self.source_filename.replace("ERRORS", "ERROS")),
        ]
        for candidate in local_candidates:
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as file_handle:
                    payload = json.load(file_handle)
                self._audit(candidate, "local_fallback", "fetched_source")
                return payload
            except Exception as exc:
                logger.debug(f"Failed to read local fallback {candidate}: {exc}")

        return None

    def load_catalog(self, force_refresh: bool = False) -> Dict[str, Procedure]:
        with self._cache_lock:
            if not force_refresh and self._catalog_is_valid():
                return dict(self._catalog_cache)

            payload = self._fetch_source_payload()
            if payload is None:
                return dict(self._catalog_cache)

            catalog = self._extract_procedures(payload)
            self._catalog_cache = catalog
            self._catalog_loaded_at = time.time()
            logger.info(f"Loaded {len(catalog)} runtime procedures from {self.source_filename}")
            return dict(catalog)

    def get_error_metadata(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a given error code/alias from the loaded catalog."""
        self.load_catalog()
        return self._error_metadata_cache.get(_normalize(error_id))

    def list_active_errors(self) -> List[Dict[str, Any]]:
        """Return all currently unresolved errors from the loaded catalog."""
        self.load_catalog()
        seen: Dict[str, Dict[str, Any]] = {}
        for key, metadata in self._error_metadata_cache.items():
            code = str(metadata.get("code", key))
            if code in seen:
                continue
            if metadata.get("needs_resolved"):
                seen[code] = metadata
        return sorted(seen.values(), key=lambda item: str(item.get("code", "")))

    def fetch_procedure(self, proc_id: str, requester: str = "local") -> Optional[Procedure]:
        catalog = self.load_catalog()
        normalized = _normalize(proc_id)

        if normalized in catalog:
            self._audit(proc_id, requester, "catalog_hit")
            return catalog[normalized]

        # Best-effort fuzzy matching for user questions that omit punctuation or
        # use variants like "bus connector" vs "LTV Bus Connector Repair".
        for key, procedure in catalog.items():
            if normalized and (normalized in key or key in normalized):
                self._audit(proc_id, requester, "catalog_fuzzy_hit")
                return procedure

        self._audit(proc_id, requester, "catalog_miss")
        return None

    def list_available_procedures(self) -> List[str]:
        catalog = self.load_catalog()
        return sorted({procedure.name for procedure in catalog.values()})


# Module-level singleton configured from env
TSS_URL = os.getenv("TSS_URL") or os.getenv("TELEMETRY_SERVER_BASE")
HMAC_SECRET = os.getenv("PROCEDURE_HMAC_SECRET")
AUDIT_LOG = os.getenv("PROCEDURE_AUDIT_LOG", os.path.join(os.getcwd(), "procedure_requests.log"))

store = ProcedureStore(
    tss_url=TSS_URL,
    hmac_secret=HMAC_SECRET,
    cache_ttl=int(os.getenv("PROCEDURE_CACHE_TTL", "300")),
    audit_log_path=AUDIT_LOG,
    source_filename=os.getenv("LTV_ERRORS_FILE", "LTV_ERRORS.json"),
)


def get_procedure(proc_id: str, requester: str = "local", fallback: Optional[Procedure] = None) -> Optional[Procedure]:
    """Public helper: try runtime TSS first, then optional fallback."""
    procedure = store.fetch_procedure(proc_id, requester=requester)
    if procedure:
        return procedure
    return fallback


def list_available_procedures() -> List[str]:
    return store.list_available_procedures()


def list_active_errors() -> List[Dict[str, Any]]:
    return store.list_active_errors()


def get_error_metadata(error_id: str) -> Optional[Dict[str, Any]]:
    return store.get_error_metadata(error_id)
