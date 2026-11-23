-- Run ONCE as the owner of source-data.app_gold (SQL Editor or notebook).
-- Replace APP_SERVICE_PRINCIPAL_APPLICATION_ID with the app's service-principal
-- application/client ID from Databricks App -> Authorization (not your user ID).
-- This public ID is not a token or secret. These grants create no tables.

GRANT USE CATALOG ON CATALOG `source-data`
TO `APP_SERVICE_PRINCIPAL_APPLICATION_ID`;

GRANT USE SCHEMA ON SCHEMA `source-data`.`app_gold`
TO `APP_SERVICE_PRINCIPAL_APPLICATION_ID`;

GRANT SELECT ON SCHEMA `source-data`.`app_gold`
TO `APP_SERVICE_PRINCIPAL_APPLICATION_ID`;
