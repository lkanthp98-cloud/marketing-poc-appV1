"""Run the built frontend and API through one Databricks Apps process."""

import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=int(os.getenv("DATABRICKS_APP_PORT", "8000")))
