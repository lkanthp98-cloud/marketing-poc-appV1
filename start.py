"""Run the built frontend and API through one Databricks Apps process."""

import os
import sys
import uvicorn


if __name__ == "__main__":
    port_val = os.getenv("DATABRICKS_APP_PORT") or os.getenv("PORT") or "8000"
    for i, arg in enumerate(sys.argv):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv):
            port_val = sys.argv[i + 1]
    host_val = "0.0.0.0"
    for i, arg in enumerate(sys.argv):
        if arg in ("--host", "-h") and i + 1 < len(sys.argv):
            host_val = sys.argv[i + 1]
    uvicorn.run("backend.main:app", host=host_val, port=int(str(port_val).strip()))
