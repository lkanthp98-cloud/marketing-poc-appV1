# Databricks notebook source
# MAGIC %md
# MAGIC # Publish the app's 30-table Gold subset
# MAGIC Run after Gold has completed, with Gold refreshes and the app paused during publication.
# MAGIC Default: `media-poc.gold` -> `source-data.app_gold`.
# MAGIC Copies 23 marts and `dim_campaign` without changing their business rows or column types.
# MAGIC Rebuilds six metadata tables so the app advertises only this subset.
# MAGIC First publication needs **30 additional table slots**. No source tables are changed,
# MAGIC no tables are dropped, and no quarantine or persistent staging tables are created.
# MAGIC The capacity check is conservative and visibility-limited, not an authoritative quota API.

# COMMAND ----------
import copy
import json
import re
import time
import uuid

MARTS = (
    'mart_application_quality_monthly',
    'mart_banking_funded_accounts_monthly',
    'mart_banking_relationship_contribution_monthly',
    'mart_brand_survey_wave',
    'mart_campaign_attribution_coverage',
    'mart_customer_acquisition_share',
    'mart_demo_campaign_economics',
    'mart_demo_experiment_comparison',
    'mart_demo_experiment_variant',
    'mart_demo_finance_reconciliation_monthly',
    'mart_demo_paid_media_daily',
    'mart_demo_relationship_value_monthly',
    'mart_demo_submission_funnel',
    'mart_demo_three_source_cost_reconciliation',
    'mart_direct_mail_performance_monthly',
    'mart_email_engagement_daily',
    'mart_new_funded_customers_monthly',
    'mart_offline_activity_monthly',
    'mart_platform_conversion_efficiency',
    'mart_sales_target_attainment_monthly',
    'mart_vendor_invoice_platform_comparison',
    'mart_vendor_media_daily',
    'mart_website_engagement_daily',
)
DIMENSIONS = ('dim_campaign',)
METADATA = (
    'gold_mart_catalog', 'gold_entity_catalog', 'gold_source_coverage',
    'gold_kpi_dictionary', 'gold_use_case_readiness', 'gold_use_case_tables',
)
DATA_TABLES = MARTS + DIMENSIONS
TABLES = DATA_TABLES + METADATA
OWNER = 'marketing-poc-appV1-app-gold-subset-v1'
REPORTED_WORKSPACE_LIMIT = 500  # User-reported workspace ceiling, not a universal product quota.


def quoted(value):
    if not value or '`' in value or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid catalog, schema, table or column identifier')
    return '`' + value + '`'


def literal(value):
    # Names and properties are not executable SQL. Reject escape-sensitive inputs.
    text = str(value)
    if any(c in text for c in ["'", '\\', '\n', '\r', '\x00']):
        raise ValueError('Use simple catalog/schema names without quotes or backslashes')
    return "'" + text + "'"


def namespace(catalog, schema):return quoted(catalog) + '.' + quoted(schema)


def references(value):
    if value is None:return []
    if isinstance(value, (list, tuple)):return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):return parsed
        except ValueError:pass
    raise ValueError('Expected an array of names in Gold metadata: ' + str(value)[:100])


def same_array_type(original, values):
    return json.dumps(values) if isinstance(original, str) else values


def require_unique(records, field, expected):
    names = [row[field] for row in records]
    if len(names) != len(set(names)) or set(names) != set(expected):
        raise ValueError('Missing or duplicate ' + field + ' inventory entries: ' + str(names))


def capacity_plan(visible_active, existing_names, ceiling=450, extra_counted_objects=0):
    if ceiling <= 0 or extra_counted_objects < 0 or visible_active < 0:
        raise ValueError('Capacity values must be nonnegative and the budget must be positive')
    if ceiling > REPORTED_WORKSPACE_LIMIT:
        raise ValueError('The object budget cannot exceed the workspace ceiling reported for this POC: 500')
    missing = sorted(set(TABLES) - set(existing_names))
    projected = visible_active + extra_counted_objects + len(missing)
    plan = dict(visible_active_objects=visible_active, extra_counted_objects=extra_counted_objects,
                new_tables=len(missing), projected_objects=projected, budget_ceiling=ceiling)
    if projected > ceiling:
        raise ValueError('Capacity check stopped publication BEFORE writes: ' + json.dumps(plan) +
            '. This subset needs additional slots; it does not reduce existing workspace tables.')
    return plan


def prepare_metadata(source, counts):
    """Rebase inventories and source-to-mart lineage without inventing upstream joins."""
    selected = set(DATA_TABLES)
    output = copy.deepcopy(source)
    output['gold_mart_catalog'] = [r for r in output['gold_mart_catalog'] if r['mart_table'] in MARTS]
    output['gold_entity_catalog'] = [r for r in output['gold_entity_catalog'] if r['gold_table'] in DIMENSIONS]
    require_unique(output['gold_mart_catalog'], 'mart_table', MARTS)
    require_unique(output['gold_entity_catalog'], 'gold_table', DIMENSIONS)
    dependencies = {}
    for row in output['gold_mart_catalog']:
        row['row_count'] = int(counts[row['mart_table']])
        dependencies[row['mart_table']] = set(re.findall(
            r'(?:mart|dim|fact|bridge|audit)_[a-z0-9_]+', str(row['model_sources'])))
    for row in output['gold_entity_catalog']:row['row_count'] = int(counts[row['gold_table']])
    output['gold_use_case_tables'] = [r for r in output['gold_use_case_tables'] if r['gold_table'] in selected]

    # Source coverage initially points to conformed Gold facts/dimensions. Connect those
    # documented dependencies to the retained marts; never advertise uncopied fact tables.
    coverage = []
    for row in output['gold_source_coverage']:
        upstream = set(references(row['gold_tables']))
        targets = (upstream & selected) | {
            mart for mart, deps in dependencies.items() if upstream & deps}
        if targets:
            row['gold_tables'] = same_array_type(row['gold_tables'], sorted(targets))
            coverage.append(row)
    output['gold_source_coverage'] = coverage
    readiness = []
    for row in output['gold_use_case_readiness']:
        original = references(row['reporting_marts'])
        kept = sorted(set(original) & set(MARTS))
        omitted = sorted(set(original) - set(MARTS))
        if not kept:continue
        row['reporting_marts'] = same_array_type(row['reporting_marts'], kept)
        if omitted:
            row['remaining_requirements'] = (str(row.get('remaining_requirements') or '') +
                '; Excluded from this app publication: ' + ', '.join(omitted)).lstrip('; ')
            row['implementation_status'] = 'limited_app_subset'
        readiness.append(row)
    output['gold_use_case_readiness'] = readiness
    active_cases = {row['use_case'] for row in readiness}
    output['gold_use_case_tables'] = [row for row in output['gold_use_case_tables'] if row['use_case'] in active_cases]
    for row in coverage:
        row['use_cases'] = same_array_type(row['use_cases'], sorted(set(references(row['use_cases'])) & active_cases))
    validate_metadata(output)
    return output


def validate_metadata(records):
    require_unique(records['gold_mart_catalog'], 'mart_table', MARTS)
    require_unique(records['gold_entity_catalog'], 'gold_table', DIMENSIONS)
    for row in records['gold_source_coverage']:
        if not set(references(row['gold_tables'])).issubset(DATA_TABLES):
            raise ValueError('Source coverage advertises an uncopied table')
    for row in records['gold_use_case_tables']:
        if row['gold_table'] not in DATA_TABLES:raise ValueError('Use-case mapping advertises an uncopied table')
    for row in records['gold_use_case_readiness']:
        if not set(references(row['reporting_marts'])).issubset(MARTS):
            raise ValueError('Readiness advertises an uncopied mart')


def create_sql(target, source_select, source_table, version, run_id):
    properties = {'marketing.app_subset.owner':OWNER, 'marketing.app_subset.source':source_table,
                  'marketing.app_subset.source_version':str(version), 'marketing.app_subset.run_id':run_id}
    return ('CREATE OR REPLACE TABLE ' + target + ' USING DELTA TBLPROPERTIES (' +
        ', '.join(literal(k) + '=' + literal(v) for k,v in properties.items()) + ') AS ' + source_select)


def validate_target(existing, details, source_name):
    if not existing:return
    if str(details.get('format', '')).lower() != 'delta':
        raise ValueError('An existing target must be a managed Delta table')
    properties = details.get('properties') or {}
    if properties.get('marketing.app_subset.owner') != OWNER or properties.get('marketing.app_subset.source') != source_name:
        raise ValueError('Refusing to replace a target not owned by this publisher: ' + source_name)

# COMMAND ----------
def run_publisher(spark, dbutils):
    started = time.monotonic()
    def log(message):print(f'[{time.monotonic()-started:7.1f}s] {message}', flush=True)
    for key,default in [('source_catalog','media-poc'), ('source_schema','gold'),
                        ('target_catalog','source-data'), ('target_schema','app_gold'),
                        ('object_budget','450'), ('extra_counted_objects','0')]:
        dbutils.widgets.text(key,default)
    dbutils.widgets.dropdown('run_mode','publish',['publish','plan'])
    config = {key:dbutils.widgets.get(key).strip() for key in [
        'source_catalog','source_schema','target_catalog','target_schema',
        'object_budget','extra_counted_objects','run_mode']}
    source_ns = namespace(config['source_catalog'],config['source_schema'])
    target_ns = namespace(config['target_catalog'],config['target_schema'])
    # Unity Catalog identifiers are case insensitive.
    if source_ns.casefold() == target_ns.casefold():
        raise ValueError('Source and target must be different schemas. No writes were made.')
    if config['target_schema'].lower() in {'bronze','silver','model','gold','dq','use_cases','usecases','information_schema'}:
        raise ValueError('Choose a dedicated app schema such as app_gold; not a pipeline source schema.')
    for key in ['source_catalog','source_schema','target_catalog','target_schema']:literal(config[key])
    if config['run_mode'] not in {'publish','plan'}:raise ValueError('Invalid run mode')
    run_id = uuid.uuid4().hex
    log('Source: ' + source_ns + '; target: ' + target_ns + '; expected objects: 30')

    # Count visible existing relations before creating even the destination schema.
    inventory = spark.sql('SELECT table_catalog, table_schema, table_name, table_type '
        'FROM system.information_schema.tables WHERE table_schema <> \'information_schema\'').collect()
    existing = {r['table_name'] for r in inventory if
        str(r['table_catalog']).casefold() == config['target_catalog'].casefold() and
        str(r['table_schema']).casefold() == config['target_schema'].casefold()}
    if existing - set(TABLES):
        raise ValueError('Target schema contains unrelated objects. Choose a dedicated empty app schema: ' +
                         ', '.join(sorted(existing-set(TABLES))))
    plan = capacity_plan(len(inventory), existing, int(config['object_budget']), int(config['extra_counted_objects']))
    log('Capacity estimate: ' + json.dumps(plan))
    log('Visibility-limited estimate; include other known counted objects in extra_counted_objects. '
        'Platform quotas and concurrent creations remain authoritative.')

    versions, schemas, frames = {}, {}, {}
    for name in TABLES:
        source = source_ns + '.' + quoted(name)
        detail = spark.sql('DESCRIBE DETAIL ' + source).first().asDict()
        if str(detail.get('format','')).lower() != 'delta':
            raise ValueError('This publisher requires Delta source tables: ' + source)
        versions[name] = int(spark.sql('DESCRIBE HISTORY ' + source + ' LIMIT 1').first()['version'])
        frames[name] = spark.sql('SELECT * FROM ' + source + ' VERSION AS OF ' + str(versions[name]))
        schemas[name] = frames[name].schema
        if name in existing:
            target = target_ns + '.' + quoted(name)
            kind = next(r['table_type'] for r in inventory if r['table_name']==name and
                str(r['table_catalog']).casefold()==config['target_catalog'].casefold() and
                str(r['table_schema']).casefold()==config['target_schema'].casefold())
            if kind != 'MANAGED':raise ValueError('Existing target is not a regular managed table: ' + target)
            validate_target(True, spark.sql('DESCRIBE DETAIL ' + target).first().asDict(),
                            config['source_catalog']+'.'+config['source_schema']+'.'+name)
        log('Pinned source ' + name + ' at Delta version ' + str(versions[name]))

    # One query counts pinned data snapshots. Business data is never collected into Python.
    counts_sql = ' UNION ALL '.join('SELECT '+literal(name)+' AS table_name, COUNT(*) AS row_count FROM '+
        source_ns+'.'+quoted(name)+' VERSION AS OF '+str(versions[name]) for name in DATA_TABLES)
    counts = {r['table_name']:int(r['row_count']) for r in spark.sql(counts_sql).collect()}
    source_metadata = {name:[r.asDict(recursive=True) for r in frames[name].collect()] for name in METADATA}
    metadata = prepare_metadata(source_metadata, counts)
    # A non-unique dimension would make downstream campaign joins unsafe.
    master = frames['dim_campaign']
    if master.where('campaign_key IS NULL').limit(1).count() or master.groupBy('campaign_key').count().where('count > 1').limit(1).count():
        raise ValueError('Gold dim_campaign has null or duplicate campaign keys. No destination writes were made.')
    # Construct metadata frames now so schema/type errors are caught before publication.
    metadata_frames = {name:spark.createDataFrame(metadata[name],schema=schemas[name]) for name in METADATA}

    def check_source_versions():
        changed = [name for name in TABLES if int(spark.sql('DESCRIBE HISTORY '+source_ns+'.'+quoted(name)+
            ' LIMIT 1').first()['version']) != versions[name]]
        if changed:raise ValueError('Gold changed during publication. Keep the app paused, complete Gold and rerun: '+', '.join(changed))
    check_source_versions()
    log('Preflight complete: 23 marts, 1 dimension, 6 narrowed metadata tables.')
    if config['run_mode']=='plan':
        log('Plan mode: no schema or tables created. Set run_mode=publish to write the subset.')
        return

    spark.sql('CREATE SCHEMA IF NOT EXISTS ' + target_ns)
    # Publish data before its inventories. No DROP/DELETE, clones, or persistent staging.
    for name in DATA_TABLES + ('gold_source_coverage','gold_kpi_dictionary','gold_use_case_readiness',
                              'gold_use_case_tables','gold_entity_catalog','gold_mart_catalog'):
        target = target_ns+'.'+quoted(name)
        source_name = config['source_catalog']+'.'+config['source_schema']+'.'+name
        temp = None
        if name in METADATA:
            temp = '_app_subset_'+run_id+'_'+name
            metadata_frames[name].createOrReplaceTempView(temp)
            select = 'SELECT * FROM '+quoted(temp)
        else:select = 'SELECT * FROM '+source_ns+'.'+quoted(name)+' VERSION AS OF '+str(versions[name])
        try:spark.sql(create_sql(target, select, source_name, versions[name], run_id))
        finally:
            if temp:spark.catalog.dropTempView(temp)
        log('Published '+target)

    # Verify exact rows (including duplicate multiplicity) and column types for all 24
    # business tables. Metadata intentionally changes membership; verify its rows separately.
    for name in TABLES:
        target = target_ns+'.'+quoted(name)
        actual = spark.table(target)
        expected = metadata_frames[name] if name in METADATA else frames[name]
        fields = lambda frame:[(f.name,f.dataType.simpleString()) for f in frame.schema.fields]
        if fields(actual) != fields(expected):raise ValueError('Column/type mismatch: '+target)
        differences = actual.exceptAll(expected).unionByName(expected.exceptAll(actual))
        if differences.limit(1).count():
            raise ValueError('Source/target row mismatch: '+target+'; keep the app paused and rerun after investigating.')
        log('Verified exact rows and types: '+name)
    check_source_versions()
    final = spark.sql('SHOW TABLES IN '+target_ns).collect()
    final_names = {r['tableName'] for r in final if not r['isTemporary']}
    if final_names != set(TABLES):raise ValueError('Destination object membership changed; expected exactly 30 tables.')
    log('SUCCESS: exactly 30 tables published and reconciled. Publication ID: '+run_id)
    print('App Connection settings: Gold catalog='+config['target_catalog']+', Gold schema='+config['target_schema'])
    print('Refresh order: Gold -> this notebook -> reopen/refresh the app. Configure Genie on this schema separately.')

# COMMAND ----------
if __name__ == '__main__':
    run_publisher(spark, dbutils)
