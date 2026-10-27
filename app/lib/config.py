"""Environment + connection config for the OMOP Review app.

Dual-mode: runs locally (Databricks CLI profile) or as a deployed Databricks App
(auto-injected service-principal credentials).
"""
import os
from functools import lru_cache
from databricks.sdk import WorkspaceClient

IS_APP = bool(os.environ.get("DATABRICKS_APP_NAME"))
PROFILE = os.environ.get("DATABRICKS_PROFILE", "pulse-azure")

# Unity Catalog (worklist + concept picker)
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "148ccb90800933a1")
CATALOG = os.environ.get("CATALOG", "vjoseph_pbi_demo")
SCHEMA = os.environ.get("SCHEMA", "omop_review")

# Lakebase (review state)
PG_ENDPOINT = os.environ.get(
    "ENDPOINT_NAME", "projects/omop-review/branches/production/endpoints/primary"
)
PG_HOST = os.environ.get("PGHOST", "")
PG_DATABASE = os.environ.get("PGDATABASE", "omop_review")
PG_USER = os.environ.get("PGUSER", "")
PG_PORT = os.environ.get("PGPORT", "5432")
PG_SSLMODE = os.environ.get("PGSSLMODE", "require")


@lru_cache(maxsize=1)
def ws() -> WorkspaceClient:
    return WorkspaceClient() if IS_APP else WorkspaceClient(profile=PROFILE)


def current_user_email() -> str:
    try:
        return ws().current_user.me().user_name
    except Exception:
        return os.environ.get("USER_EMAIL", "unknown@databricks.com")
