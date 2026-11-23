# Databricks notebook source
# MAGIC %md
# MAGIC # Read-only Gold campaign and filter integrity audit
# MAGIC Run against the Gold location used by the app. This notebook displays results only;
# MAGIC it creates no tables, views or quarantine outputs. Unresolved mappings are reported
# MAGIC separately from invalid references and must not be guessed from names.

# COMMAND ----------
import json
import re

dbutils.widgets.text('gold_catalog', 'media-poc')
dbutils.widgets.text('gold_schema', 'gold')

def quoted(value):
    if not value or '`' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid catalog, schema, table or column name')
    return '`' + value + '`'

namespace = '.'.join(quoted(dbutils.widgets.get(key)) for key in ['gold_catalog', 'gold_schema'])
def gold(name):return namespace + '.' + quoted(name)
def bad_name(field):
    return f"({field} IS NULL OR LOWER(TRIM(CAST({field} AS STRING))) IN ('', 'unknown', 'null', 'none'))"

# COMMAND ----------
# MAGIC %md
# MAGIC Duplicate master keys are unsafe for fact joins even when their names agree.
# MAGIC The app resolves filter labels without joining the dimension onto fact measures.

# COMMAND ----------
master = gold('dim_campaign')
master_columns = set(spark.table(master).columns)
name_field = 'campaign_name' if 'campaign_name' in master_columns else 'campaign_title'
name = quoted(name_field)
display(spark.sql(f"""
SELECT campaign_key, COUNT(*) AS master_rows, COUNT(DISTINCT {name}) AS distinct_names,
       COLLECT_SET({name}) AS names
FROM {master} GROUP BY campaign_key
HAVING COUNT(*) > 1 OR campaign_key IS NULL
"""))
display(spark.sql(f"""
SELECT campaign_key, {name} AS campaign_name FROM {master}
WHERE {bad_name(name)} OR TRIM(CAST({name} AS STRING)) = TRIM(CAST(campaign_key AS STRING))
"""))

# COMMAND ----------
# MAGIC %md
# MAGIC Each report below shows the dataset's real filter keys, unresolved rows, references
# MAGIC absent from the campaign master, conflicting labels and duplicate declared grains.
# MAGIC Missing campaign/platform fields explain unavailable filters in the app; they are
# MAGIC not automatically upstream defects. An unresolved row may be valid pending approval.

# COMMAND ----------
reports = []
for entry in spark.table(gold('gold_mart_catalog')).collect():
    row = entry.asDict()
    table_name = row['mart_table']
    try:
        table = gold(table_name)
        columns = set(spark.table(table).columns)
        key = next((c for c in ['resolved_campaign_key', 'campaign_key'] if c in columns), None)
        raw_grain = row['grain_columns']
        if isinstance(raw_grain, list):grain = raw_grain
        else:
            try:grain = json.loads(raw_grain)
            except (TypeError, ValueError):grain = re.split(r'[\s,]+', str(raw_grain).strip())
        if not isinstance(grain, list):raise ValueError('Unrecognized grain metadata')
        grain = [str(c).strip('`') for c in grain if str(c).strip('`')]
        if not grain or not set(grain).issubset(columns):
            raise ValueError('Declared grain columns are missing or empty: ' + str(grain))
        keys = ', '.join(quoted(c) for c in grain)
        duplicates = spark.sql(f'SELECT COUNT(*) AS n FROM (SELECT {keys} FROM {table} '
            f'GROUP BY {keys} HAVING COUNT(*) > 1) duplicate_grains').first()['n']
        total = spark.sql(f'SELECT COUNT(*) AS n FROM {table}').first()['n']
        unresolved = missing = mismatches = None
        if key:
            k = quoted(key)
            unresolved = spark.sql(f'SELECT COUNT(*) AS n FROM {table} WHERE {bad_name(k)}').first()['n']
            # Compare distinct nonblank keys; do not fan out facts on duplicate master rows.
            missing = spark.sql(f'''SELECT COUNT(*) AS n FROM (
                SELECT DISTINCT {k} AS campaign_key FROM {table} WHERE NOT {bad_name(k)}
                EXCEPT SELECT DISTINCT campaign_key FROM {master}
            ) absent_master_keys''').first()['n']
            if 'campaign_name' in columns:
                mismatches = spark.sql(f'''SELECT COUNT(*) AS n FROM {table} t
                    JOIN (SELECT campaign_key, MIN({name}) AS campaign_name FROM {master}
                          GROUP BY campaign_key HAVING COUNT(*) = 1) d
                    ON t.{k} = d.campaign_key
                    WHERE NOT {bad_name('t.campaign_name')} AND NOT {bad_name('d.campaign_name')}
                      AND TRIM(t.campaign_name) <> TRIM(d.campaign_name)''').first()['n']
        reports.append({'table':table_name,'rows':str(total),'campaign_filter_key':key or 'UNSUPPORTED',
            'platform_filter':'platform' if 'platform' in columns else 'UNSUPPORTED',
            'unresolved_campaign_rows':str(unresolved),'distinct_keys_missing_from_master':str(missing),
            'mart_name_mismatch_rows':str(mismatches),'duplicate_grain_groups':str(duplicates),'error':''})
    except Exception as error:
        reports.append({'table':table_name,'error':str(error)[:1000]})

fields = ['table','rows','campaign_filter_key','platform_filter','unresolved_campaign_rows',
          'distinct_keys_missing_from_master','mart_name_mismatch_rows','duplicate_grain_groups','error']
display(spark.createDataFrame([tuple(row.get(field) for field in fields) for row in reports],
    ', '.join(field + ' STRING' for field in fields)))
print('Read-only audit completed. Review errors and mapping status; no data was published or changed.')
