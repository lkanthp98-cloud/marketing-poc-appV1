"""Read-only SQL access with isolated preview data and viewer-scoped live queries."""

import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from dataclasses import dataclass
from contextvars import ContextVar
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
WORKSPACE_CONTRACT = json.loads((APP_ROOT / "data" / "workspace_contract.json").read_text(encoding="utf-8"))
ANALYTICS_MAPPING = WORKSPACE_CONTRACT["analytics_mapping"]
ACTIVE_CONNECTION = ContextVar("marketing_connection", default={})
USE_CASE_NAMES = {spec["name"] for spec in WORKSPACE_CONTRACT["tables"].values()
                  if (spec["catalog"], spec["schema"]) == ("source-data", "usecases")}


class DataError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def identifier(value):
    if not IDENTIFIER.fullmatch(value):
        raise DataError("Choose a table or column from the published catalog.", 400)
    return "`" + value + "`"


def normalize_workspace_host(value):
    value=value.strip().rstrip('/')
    if not value:return ''
    if '://' not in value:value='https://'+value
    parts=urlsplit(value)
    if (parts.scheme.lower()!='https' or not parts.hostname or parts.username or parts.password
            or parts.path not in {'','/'} or parts.query or parts.fragment
            or any(c.isspace() or ord(c)<32 for c in value)):
        raise ValueError('Use the HTTPS workspace origin, without credentials, a path or query string.')
    # Reading .port also validates malformed ports before any request is made.
    parts.port
    return 'https://'+parts.netloc


def normalize_json(value):
    if isinstance(value, str) and value[:1] in {"[", "{"}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value


_preview_lock = threading.Lock()
_preview_path = None


def preview_database():
    global _preview_path
    with _preview_lock:
        if _preview_path is None:
            archive = APP_ROOT / "data" / "preview.db.gz"
            if not archive.exists():
                raise DataError("The local preview dataset is missing. Run scripts/build_preview.py first.")
            handle, name = tempfile.mkstemp(prefix="marketing-preview-", suffix=".db")
            os.close(handle)
            with gzip.open(archive, "rb") as compressed, open(name, "wb") as output:
                output.write(compressed.read())
            _preview_path = Path(name)
        return _preview_path


@dataclass(frozen=True)
class Viewer:
    token: str = ""
    label: str = "Local preview"

    @property
    def cache_key(self):
        return hashlib.sha256(self.token.encode()).hexdigest()


class Store:
    def __init__(self):
        self.mode = os.getenv("DATA_MODE", "preview").lower()
        if self.mode not in {"live", "preview"}:
            raise RuntimeError("DATA_MODE must be live or preview.")
        if os.getenv("DATABRICKS_APP_NAME") and self.mode != "live":
            raise RuntimeError("A deployed Databricks app must explicitly use DATA_MODE=live.")
        self._defaults = {"gold_catalog":os.getenv("GOLD_CATALOG", "media-poc"),
            "gold_schema":os.getenv("GOLD_SCHEMA", "gold"),
            "use_cases_catalog":'',
            "use_cases_schema":''}
        self._host_present=bool(os.getenv('DATABRICKS_HOST','').strip())
        self._host_invalid=False
        try:self.host=normalize_workspace_host(os.getenv('DATABRICKS_HOST',''))
        except ValueError:self.host='';self._host_invalid=True
        # The package uses DATABRICKS_WAREHOUSE_ID. Also support explicitly configured
        # alternative names used in Databricks examples; do not infer a different resource.
        self.warehouse_env=next((name for name in ('DATABRICKS_WAREHOUSE_ID','DATABRICKS_SQL_WAREHOUSE_ID','WAREHOUSE_ID')
            if os.getenv(name,'').strip()),'')
        self.warehouse=os.getenv(self.warehouse_env,'').strip() if self.warehouse_env else ''
        self._schema_cache = {}
        self._lock = threading.Lock()
        # Use-case pages are application projections of Gold, never a second publication.
        self.default_source_mode='gold'

    @property
    def catalog(self):return ACTIVE_CONNECTION.get().get("gold_catalog",self._defaults["gold_catalog"])
    @property
    def schema(self):return ACTIVE_CONNECTION.get().get("gold_schema",self._defaults["gold_schema"])
    @property
    def use_cases_catalog(self):return ACTIVE_CONNECTION.get().get("use_cases_catalog",self._defaults["use_cases_catalog"])
    @property
    def use_cases_schema(self):return ACTIVE_CONNECTION.get().get("use_cases_schema",self._defaults["use_cases_schema"])

    def connection(self):
        return {"gold_catalog":self.catalog,"gold_schema":self.schema,
                "use_cases_catalog":self.use_cases_catalog,"use_cases_schema":self.use_cases_schema,
                "source_mode":self.source_mode}

    @property
    def source_mode(self):return 'gold'

    @property
    def analytics_layer(self):return 'gold'

    def layer_enabled(self,layer):return layer=='gold'

    def location(self, name, layer=None):
        identifier(name)
        if layer is None:
            layer = self.analytics_layer if name in ANALYTICS_MAPPING else 'use_cases' if name in USE_CASE_NAMES else 'gold'
        if layer not in {"gold", "use_cases"}:
            raise DataError("Choose the Gold data source.", 400)
        if not self.layer_enabled(layer):raise DataError(f'The {layer} source is disabled in this connection.',400)
        return self.catalog, self.schema, name

    def table(self, name, layer=None):
        catalog, schema, physical = self.location(name, layer)
        safe = identifier(physical)
        if self.mode == "preview":
            return safe
        parts = [catalog, schema]
        if any(not part or "`" in part for part in parts):
            raise DataError("The configured catalog or schema is invalid.")
        return ".".join("`" + part + "`" for part in parts) + "." + safe

    def logical_name(self, name):
        return next((source for source,target in ANALYTICS_MAPPING.items() if target == name), name)

    def source_label(self, name, layer=None):
        return ".".join(self.location(name, layer))

    def runtime_status(self):
        return {'build':'2026-11-23-app-gold-subset','mode':self.mode,'source_mode':self.source_mode,
            'workspace_host_present':self._host_present,'workspace_host_valid':bool(self.host),
            'warehouse_id_present':bool(self.warehouse),'warehouse_environment_variable':self.warehouse_env or None,
            'expected_warehouse_resource_key':'sql-warehouse','genie_space_present':bool(os.getenv('GENIE_SPACE_ID','').strip())}

    def validate_runtime(self,require_warehouse=True):
        if not self.host:
            if self._host_invalid:
                raise DataError('DATABRICKS_HOST is invalid. Use the workspace hostname or HTTPS workspace origin, without a path or query string.')
            raise DataError('DATABRICKS_HOST is missing from the running app. Redeploy using the Databricks Apps runtime; the platform supplies this variable.')
        if require_warehouse and not self.warehouse:
            raise DataError('The warehouse ID was not injected into the running app. The attached warehouse resource key must match app.yaml valueFrom: sql-warehouse, mapped to DATABRICKS_WAREHOUSE_ID. Redeploy the app after changing Resources or app.yaml.')

    def _request(self, path, token, body=None):
        self.validate_runtime()
        if not token:
            raise DataError("Enable Databricks user authorization with the SQL scope and reopen the app.", 401)
        if not path.startswith("/api/2.0/sql/statements"):
            raise DataError("Invalid warehouse response path.")
        payload = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.host + path, data=payload, headers={
            "Authorization": "Bearer " + token, "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                raise DataError(f'Databricks SQL API rejected this request (HTTP {error.code}). Enable the sql user-authorization scope and consent again; the signed-in user also needs CAN USE on the attached warehouse. An app service-principal resource grant alone does not grant the viewer access.',error.code) from error
            raise DataError("The warehouse could not complete this request. Check the Gold publication and warehouse status.") from error
        except (OSError, ValueError) as error:
            raise DataError("The SQL warehouse is unavailable. Retry after checking its status.") from error

    def query(self, sql, parameters, viewer):
        if self.mode == "preview":
            sql = sql.replace(" AS STRING)", " AS TEXT)")
            connection = sqlite3.connect(preview_database().as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                return [dict(row) for row in connection.execute(sql, parameters).fetchall()]
            except sqlite3.Error as error:
                raise DataError("The preview query could not be completed: " + str(error)) from error
            finally:
                connection.close()

        typed = [{"name": key, "value": str(value), "type": "STRING"} for key, value in parameters.items()]
        result = self._request("/api/2.0/sql/statements", viewer.token, {
            "warehouse_id": self.warehouse, "statement": sql, "parameters": typed,
            "format": "JSON_ARRAY", "disposition": "INLINE", "wait_timeout": "10s",
            "on_wait_timeout": "CONTINUE",
        })
        statement_id = result["statement_id"]
        deadline = time.monotonic() + 35
        while result.get("status", {}).get("state") in {"PENDING", "RUNNING"}:
            if time.monotonic() >= deadline:
                self._request(f"/api/2.0/sql/statements/{statement_id}/cancel", viewer.token, {})
                raise DataError("The warehouse query timed out. Try a narrower period or retry after warehouse startup.", 504)
            time.sleep(0.4)
            result = self._request(f"/api/2.0/sql/statements/{statement_id}", viewer.token)
        if result.get("status", {}).get("state") != "SUCCEEDED":
            detail=result.get('status',{}).get('error',{})
            code=str(detail.get('error_code','QUERY_FAILED'))
            message=str(detail.get('message','Check table publication, schema and read permissions.'))[:1000]
            raise DataError(f'SQL execution failed [{code}]: {message}',403 if 'PERMISSION' in code else 503)
        columns = result.get("manifest", {}).get("schema", {}).get("columns", [])
        output = []
        chunk = result.get("result") or {}
        while True:
            for values in chunk.get("data_array", []):
                row = {}
                for column, value in zip(columns, values):
                    kind = column.get("type_name", "")
                    if value is not None:
                        if kind in {"BYTE", "SHORT", "INT", "LONG"}:
                            value = int(value)
                        elif kind in {"DECIMAL", "DOUBLE", "FLOAT"}:
                            value = float(value)
                        elif kind == "BOOLEAN":
                            value = value == "true"
                    row[column["name"]] = value
                output.append(row)
            next_path = chunk.get("next_chunk_internal_link")
            if not next_path:
                return output
            chunk = self._request(next_path, viewer.token)

    def columns(self, name, viewer, layer=None):
        catalog_name, schema_name, physical_name = self.location(name, layer)
        key = (viewer.cache_key, catalog_name, schema_name, physical_name)
        with self._lock:
            cached = self._schema_cache.get(key)
            if cached and cached[0] > time.monotonic():
                return cached[1]
        if self.mode == "preview":
            rows = self.query(f"PRAGMA table_info({identifier(physical_name)})", {}, viewer)
            columns = [{"name": row["name"], "type": row["type"]} for row in rows]
        else:
            catalog = "`" + catalog_name.replace("`", "``") + "`"
            columns = self.query(
                f"SELECT column_name AS name, full_data_type AS type FROM {catalog}.information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :name ORDER BY ordinal_position",
                {"schema": schema_name, "name": physical_name}, viewer)
        if not columns:
            raise DataError(f"Publish {catalog_name}.{schema_name}.{physical_name} before opening this view.", 404)
        with self._lock:
            if len(self._schema_cache) > 400:
                self._schema_cache.clear()
            self._schema_cache[key] = (time.monotonic() + 60, columns)
        return columns
