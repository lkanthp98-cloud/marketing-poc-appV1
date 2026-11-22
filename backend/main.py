import csv
import datetime as dt
import io
import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .catalog import DATE_FIELDS, DEMO_CAMPAIGN_TABLES, META_TABLES, MONTHLY, PAGES
from . import genie
from .store import ACTIVE_CONNECTION, WORKSPACE_CONTRACT, ANALYTICS_MAPPING, USE_CASE_NAMES, APP_ROOT, DataError, Store, Viewer, identifier, normalize_json


store = Store()
app = FastAPI(title="Marketing Intelligence", docs_url=None, redoc_url=None)
logger = logging.getLogger("marketing_app")


class ConnectionSettings(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_mode:Literal['gold','use_cases','both']='both'
    gold_catalog: str = Field(default='',max_length=255)
    gold_schema: str = Field(default='',max_length=255)
    use_cases_catalog: str = Field(default='',max_length=255)
    use_cases_schema: str = Field(default='',max_length=255)

    def profile(self):
        values={key:value.strip() for key,value in self.model_dump().items()}
        active=(['gold_catalog','gold_schema'] if self.source_mode=='gold' else
            ['use_cases_catalog','use_cases_schema'] if self.source_mode=='use_cases' else
            ['gold_catalog','gold_schema','use_cases_catalog','use_cases_schema'])
        if any(not values[key] or "`" in values[key] or any(ord(c)<32 for c in values[key]) for key in active):
            raise DataError("Enter valid catalog and schema names.",400)
        for key in set(values)-set(active)-{'source_mode'}:values[key]=''
        return values


@app.exception_handler(DataError)
async def data_error(request, error):
    return JSONResponse(status_code=error.status, content={"detail": str(error)})


@app.middleware("http")
async def security_headers(request, call_next):
    profile={}
    cookie=request.cookies.get("marketing_connection")
    if cookie and store.mode=="live":
        try:profile=ConnectionSettings.model_validate_json(cookie).profile()
        except Exception:return JSONResponse(status_code=400,content={"detail":"The saved connection is invalid. Clear this site's connection cookie and retry."})
    context_token=ACTIVE_CONNECTION.set(profile)
    try:response = await call_next(request)
    finally:ACTIVE_CONNECTION.reset(context_token)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


def viewer(request: Request):
    if store.mode == "preview":
        return Viewer()
    token = request.headers.get("x-forwarded-access-token", "")
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
    if not token:
        token = store.get_service_principal_token()
    if not token:
        raise DataError("Sign in through Databricks Apps and enable user authorization with the SQL scope.", 401)
    label = (request.headers.get("x-forwarded-email") or
             request.headers.get("x-forwarded-preferred-username") or
             request.headers.get("x-forwarded-user") or
             "Databricks viewer")
    return Viewer(token, label)


def query_filters(
    start: str = "", end: str = "", campaign: str = "", platform: str = "", product: str = "",
    market: str = "", currency: str = "USD", plan: str = "", compare: bool = False,
):
    for value in (start, end):
        if value:
            try:
                if dt.date.fromisoformat(value).isoformat() != value:
                    raise ValueError("Noncanonical date")
            except ValueError as error:
                raise DataError("Dates must use YYYY-MM-DD.", 400) from error
    if start and end and start > end:
        raise DataError("Start date must be on or before the end date.", 400)
    values = dict(start=start, end=end, campaign=campaign, platform=platform, product=product,
                  market=market, currency=currency, plan=plan, compare=compare)
    if any(len(str(value)) > 160 for value in values.values()):
        raise DataError("A filter value is too long.", 400)
    return values


def table_catalog(user, layer="gold"):
    if not store.layer_enabled(layer):return []
    if layer == "use_cases":
        records = store.query(f"SELECT * FROM {store.table('use_case_dataset_catalog')}", {}, user)
        rows = []
        for record in records:
            name = record["dataset_table"]
            if name not in USE_CASE_NAMES: continue
            grain = normalize_json(record["grain_columns"])
            rows.append({"name":name,"kind":"mart","grain":", ".join(grain) if isinstance(grain,list) else str(grain),
                "rows":record["published_row_count"],"note":record["metric_notes"],"sources":record["model_sources"],
                "source_gold_table":record["source_gold_table"],"publication_id":record["publication_id"],
                "location":store.source_label(name,"use_cases")})
        rows.extend({"name":name,"kind":"metadata","grain":"Documented publication metadata grain","rows":None,
            "note":"Use Cases delivery and business readiness metadata.","sources":"Use Cases publication",
            "location":store.source_label(name,"use_cases")} for name in ["use_case_dataset_catalog","use_case_readiness"])
        return sorted(rows,key=lambda row:row["name"])
    marts = store.query(f"SELECT * FROM {store.table('gold_mart_catalog')}", {}, user)
    entities = store.query(f"SELECT * FROM {store.table('gold_entity_catalog')}", {}, user)
    rows = []
    for row in marts:
        rows.append({"name": row["mart_table"], "kind": "mart", "grain": row["grain_columns"],
                     "rows": row["row_count"], "note": row["metric_notes"], "sources": row["model_sources"]})
    for row in entities:
        name = row["gold_table"]
        kind = "dimension" if name.startswith("dim_") else "fact" if name.startswith("fact_") else "reference"
        rows.append({"name": name, "kind": kind, "grain": row["grain_columns"],
                     "rows": row["row_count"], "note": row["note"], "sources": row["model_table"]})
    rows.extend({"name": name, "kind": "metadata", "grain": "Documented metadata grain", "rows": None,
                 "note": "Published Gold definitions and source coverage.", "sources": "Gold publication"} for name in META_TABLES)
    return sorted([{**row,"location":store.source_label(row["name"],"gold")} for row in rows], key=lambda row: row["name"])


def require_table(name, user, layer="gold"):
    if name not in {row["name"] for row in table_catalog(user,layer)}:
        raise DataError("Choose a published table from the selected catalog.", 404)


def filter_sql(name, filters, user, layer=None):
    columns = {col["name"] for col in store.columns(name, user, layer)}
    logical = store.logical_name(name)
    terms, params, unsupported = [], {}, []
    date = DATE_FIELDS.get(logical)
    if date is None:
        date = next((col for col in ("report_date", "calendar_date", "opened_date", "value_month", "event_at") if col in columns), None)
    for key, op in (("start", ">="), ("end", "<=")):
        value = filters.get(key)
        if value and date:
            if logical in MONTHLY:
                value = value[:7] + "-01"
            terms.append(f"{identifier(date)} {op} :{key}")
            params[key] = value
        elif value:
            unsupported.append("period")
    campaign_column = "campaign_key" if logical in DEMO_CAMPAIGN_TABLES else "resolved_campaign_key"
    mappings = {
        "campaign": [campaign_column], "platform": ["platform", "source_channel"],
        "product": ["product_id"], "market": ["market_id", "booking_market_id", "market_cd", "market_code"],
        "currency": ["currency", "cost_currency"], "plan": ["plan_version"],
    }
    usd_tables = {"mart_banking_relationship_contribution_monthly", "mart_demo_relationship_value_monthly",
                  "mart_demo_campaign_economics", "mart_demo_campaign_budget_utilization"}
    for key, candidates in mappings.items():
        value = filters.get(key)
        if not value:
            continue
        column = next((field for field in candidates if field in columns), None)
        if column:
            terms.append(f"{identifier(column)} = :{key}")
            params[key] = value
        elif key == "currency" and logical in usd_tables:
            if value != "USD":
                terms.append("1 = 0")
        elif key == "currency" and not any("amount" in field or "spend" in field or "cost" in field for field in columns):
            continue
        elif key == "plan":
            continue
        else:
            unsupported.append(key)
    # A single plan is always used when actuals repeat across plan versions.
    if "plan_version" in columns and not filters.get("plan"):
        plans = store.query(f"SELECT DISTINCT plan_version FROM {store.table(name,layer)} ORDER BY plan_version DESC", {}, user)
        if plans:
            terms.append("plan_version = :default_plan")
            params["default_plan"] = plans[0]["plan_version"]
    return (" WHERE " + " AND ".join(terms) if terms else ""), params, sorted(set(unsupported))


def clean_number(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def previous_period(filters, monthly=False):
    if not filters.get("start") or not filters.get("end"):
        return None
    start, end = dt.date.fromisoformat(filters["start"]), dt.date.fromisoformat(filters["end"])
    if monthly:
        months = (end.year - start.year) * 12 + end.month - start.month + 1
        prior_month = start.year * 12 + start.month - 1 - months
        prior_start = dt.date(prior_month // 12, prior_month % 12 + 1, 1)
        return {**filters, "start": prior_start.isoformat(),
                "end": (start.replace(day=1) - dt.timedelta(days=1)).isoformat()}
    days = (end - start).days + 1
    return {**filters, "start": (start - dt.timedelta(days=days)).isoformat(),
            "end": (start - dt.timedelta(days=1)).isoformat()}


def metric_value(metric, filters, user):
    where, params, unsupported = filter_sql(metric.table, filters, user)
    rows = store.query(f"SELECT {metric.expression} AS value FROM {store.table(metric.table)}{where}", params, user)
    return clean_number(rows[0]["value"]), unsupported


def chart_data(spec, filters, user):
    where, params, unsupported = filter_sql(spec.table, filters, user)
    dimensions = [f"COALESCE(CAST({identifier(field)} AS STRING), 'Unresolved') AS {identifier('label' if i == 0 else 'group')}"
                  for i, field in enumerate(spec.dimensions)]
    measures = [m["expression"] + " AS " + identifier(m["name"]) for m in spec.measures]
    group = ""
    if spec.dimensions and not spec.raw:
        group = " GROUP BY " + ", ".join(identifier(field) for field in spec.dimensions)
    order = " ORDER BY " + spec.order if spec.dimensions else ""
    rows = store.query(f"SELECT {', '.join(dimensions + measures)} FROM {store.table(spec.table)}{where}{group}{order} LIMIT {spec.limit}", params, user)
    return {"title": spec.title, "kind": spec.kind, "dimensions": list(spec.dimensions),
            "measures": [{k: v for k, v in m.items() if k != "expression"} for m in spec.measures],
            "note": spec.note, "unsupported_filters": unsupported,
            "rows": [{key: clean_number(value) for key, value in row.items()} for row in rows],
            "table":store.location(spec.table,store.analytics_layer)[2],"source":store.source_label(spec.table,store.analytics_layer)}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": store.mode,
        "workspace_host_valid": bool(store.host),
        "warehouse_id_present": bool(store.warehouse),
    }


@app.get('/api/runtime-config')
def runtime_config(user:Viewer=Depends(viewer)):
    # Report presence and binding names only, never environment values or credentials.
    return store.runtime_status()


@app.get("/api/bootstrap")
def bootstrap(user: Viewer = Depends(viewer)):
    catalog = table_catalog(user)
    use_cases = table_catalog(user,"use_cases")
    analytics= catalog if store.analytics_layer=='gold' else use_cases
    available={row['name'] for row in analytics}
    warnings=[]
    def has(name):return store.location(name,store.analytics_layer)[2] in available
    def safe_query(sql,params=None):
        try:return store.query(sql,params or {},user)
        except DataError as error:
            warnings.append(str(error));return []
    def options(table, field):
        if not has(table):return []
        try:columns={c['name'] for c in store.columns(table,user)}
        except DataError as error:warnings.append(str(error));return []
        if field not in columns:return []
        return [row["value"] for row in safe_query(
            f"SELECT DISTINCT {identifier(field)} AS value FROM {store.table(table)} WHERE {identifier(field)} IS NOT NULL ORDER BY {identifier(field)}")]
    # Reference filters come from the selected analytics source; Use Cases never requires Gold dimensions.
    campaigns={}
    for source in ['mart_vendor_media_daily','mart_demo_campaign_economics','mart_new_funded_customers_monthly']:
        if not has(source):continue
        try:columns={c['name'] for c in store.columns(source,user)}
        except DataError as error:warnings.append(str(error));continue
        key='campaign_key' if source in DEMO_CAMPAIGN_TABLES else 'resolved_campaign_key'
        if key not in columns:continue
        label=f"COALESCE(campaign_name, CAST({identifier(key)} AS STRING))" if 'campaign_name' in columns else f"CAST({identifier(key)} AS STRING)"
        for row in safe_query(f"SELECT DISTINCT {identifier(key)} AS campaign_key, {label} AS campaign_name FROM {store.table(source)} WHERE {identifier(key)} IS NOT NULL"):
            campaigns[row['campaign_key']]=row
    date_sources = " UNION ALL ".join(
        f"SELECT {identifier(field)} AS report_day FROM {store.table(table)}" for table, field in DATE_FIELDS.items() if table in ANALYTICS_MAPPING and has(table))
    date_rows=safe_query("SELECT MIN(report_day) AS start, MAX(report_day) AS end FROM ("+date_sources+") report_dates") if date_sources else []
    dates=date_rows[0] if date_rows else {'start':'','end':''}
    dates={key:(str(value)[:10] if value else '') for key,value in dates.items()}
    coverage=safe_query(f"SELECT COUNT(*) AS sources FROM {store.table('gold_source_coverage','gold')}") if store.layer_enabled('gold') else []
    return {"mode": store.mode, "viewer": user.label, "catalog": store.catalog, "schema": store.schema,
            "source_mode":store.source_mode,"enabled_sources":[layer for layer in ['gold','use_cases'] if store.layer_enabled(layer)],
            "analytics_layer":store.analytics_layer,"warnings":list(dict.fromkeys(warnings)),
            "analytics_catalog":store.catalog if store.analytics_layer=='gold' else store.use_cases_catalog,
            "analytics_schema":store.schema if store.analytics_layer=='gold' else store.use_cases_schema,"use_case_tables":use_cases,
            "tables": catalog, "sources": coverage[0]["sources"] if coverage else None, "dates": dates, "campaigns": list(campaigns.values()),
            "platforms": options(VENDOR_TABLE, "platform"),
            "products": options("mart_banking_funded_accounts_monthly", "product_id"), "markets": options("mart_banking_funded_accounts_monthly", "market_id"),
            "currencies": options(VENDOR_TABLE, "currency"), "plans": options("mart_sales_target_attainment_monthly", "plan_version"),
            "pages": [{"id": key, "title": value["title"], "subtitle": value["subtitle"]} for key, value in PAGES.items()]}


VENDOR_TABLE = "mart_vendor_media_daily"


@app.get("/api/dashboard/{page}")
def dashboard(page: str, filters: dict = Depends(query_filters), user: Viewer = Depends(viewer)):
    if page not in PAGES:
        raise DataError("Unknown dashboard page.", 404)
    spec = PAGES[page]
    published={row['name'] for row in table_catalog(user,store.analytics_layer)}
    def card(metric):
        unavailable=None
        try:
            if store.location(metric.table,store.analytics_layer)[2] not in published:
                raise DataError('This dataset is not registered in the selected publication.',404)
            value, unsupported = metric_value(metric, filters, user)
            previous = previous_period(filters, metric.table in MONTHLY) if filters.get("compare") and "period" not in unsupported else None
            prior = metric_value(metric, previous, user)[0] if previous else None
        except DataError as error:value=None;prior=None;unsupported=[];unavailable=str(error)
        change = (value - prior) / abs(prior) if value is not None and prior not in {None, 0} else None
        return {"label": metric.label, "value": value, "format": metric.format, "description": metric.description,
                "table": store.location(metric.table,store.analytics_layer)[2], "source":store.source_label(metric.table,store.analytics_layer),
                "change": change, "previous": prior, "direction": metric.direction,
                "unsupported_filters": unsupported,"unavailable_reason":unavailable}
    def safe_chart(chart):
        try:
            if store.location(chart.table,store.analytics_layer)[2] not in published:
                raise DataError('This dataset is not registered in the selected publication.',404)
            return chart_data(chart,filters,user)
        except DataError as error:
            return {'title':chart.title,'kind':chart.kind,'table':store.location(chart.table,store.analytics_layer)[2],
                'source':store.source_label(chart.table,store.analytics_layer),'dimensions':list(chart.dimensions),
                'measures':[{k:v for k,v in m.items() if k!='expression'} for m in chart.measures],
                'note':chart.note,'unsupported_filters':[],'rows':[],'unavailable_reason':str(error)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        context=copy_context()
        cards = list(pool.map(lambda metric:context.copy().run(card,metric), spec["metrics"]))
        charts = list(pool.map(lambda chart:context.copy().run(safe_chart,chart), spec["charts"]))
    candidates=[store.location(spec['table'],store.analytics_layer)[2]]+[c['table'] for c in cards]+[c['table'] for c in charts]
    records=next((name for name in candidates if name in published),'')
    return {"title": spec["title"], "subtitle": spec["subtitle"], "eyebrow": spec["eyebrow"],
            "metrics": cards, "charts": charts, "table":records,
            "source":store.source_label(records,store.analytics_layer) if records else '',"mode": store.mode}


@app.get("/api/table/{name}")
def table_rows(name: str, filters: dict = Depends(query_filters), user: Viewer = Depends(viewer),
               page: int = Query(0, ge=0, le=100000), size: int = Query(20, ge=1, le=100),
               sort: str = "", descending: bool = True, search: str = Query("", max_length=120),
               layer: Literal["gold","use_cases"] = "gold"):
    require_table(name, user, layer)
    schema = store.columns(name, user, layer)
    names = [column["name"] for column in schema]
    if sort and sort not in names:
        raise DataError("Choose a sort column from this table.", 400)
    where, params, unsupported = filter_sql(name, filters, user, layer)
    where, params = search_sql(schema, where, params, search)
    # Stable ties prevent OFFSET pagination from moving between equivalent sort values.
    scalar_columns = [column["name"] for column in schema
                      if not any(kind in column["type"].upper() for kind in ("ARRAY", "MAP", "STRUCT", "BINARY"))]
    order_columns = ([sort] if sort else []) + [column for column in scalar_columns if column != sort]
    direction = " DESC" if descending else " ASC"
    order = " ORDER BY " + ", ".join(identifier(column) + direction for column in order_columns)
    count = store.query(f"SELECT COUNT(*) AS total FROM {store.table(name,layer)}{where}", params, user)[0]["total"]
    rows = store.query(f"SELECT * FROM {store.table(name,layer)}{where}{order} LIMIT {size} OFFSET {page * size}", params, user)
    return {"name": name, "source":store.source_label(name,layer),"schema": schema, "rows": rows, "total": count, "page": page, "size": size,
            "unsupported_filters": unsupported}


def search_sql(schema, where, params, search):
    if search:
        text_columns = [column["name"] for column in schema if any(kind in column["type"].upper() for kind in ("STRING", "TEXT"))]
        if text_columns:
            clause = "(" + " OR ".join(f"LOWER(CAST({identifier(column)} AS STRING)) LIKE :search" for column in text_columns) + ")"
            where += (" AND " if where else " WHERE ") + clause
            params["search"] = "%" + search.lower() + "%"
    return where, params


@app.get("/api/export/{name}")
def export_csv(name: str, filters: dict = Depends(query_filters), user: Viewer = Depends(viewer),
               search: str = Query("", max_length=120), layer: Literal["gold","use_cases"] = "gold"):
    require_table(name, user, layer)
    schema = store.columns(name, user, layer)
    where, params, _ = filter_sql(name, filters, user, layer)
    where, params = search_sql(schema, where, params, search)
    rows = store.query(f"SELECT * FROM {store.table(name,layer)}{where} LIMIT 10000", params, user)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([column["name"] for column in schema])
    for row in rows:
        values = []
        for column in schema:
            value = row.get(column["name"])
            if isinstance(value, (list, dict)):
                value = json.dumps(value)
            if isinstance(value, str) and (value.lstrip()[:1] in {"=", "+", "-", "@"} or value[:1] in {"\t", "\r", "\n"}):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return Response(output.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{name}-filtered.csv"', "X-Export-Limit": "10000"})


@app.get("/api/metadata/{kind}")
def metadata(kind: str, user: Viewer = Depends(viewer)):
    if kind=='lineage' and not store.layer_enabled('gold'):return []
    if kind=='metrics' and not store.layer_enabled('gold'):
        return [{'metric_id':page+'_'+str(i),'business_definition':metric.description,'formula':metric.expression,
            'definition_source':'Application reporting reference; no Gold policy approval is implied.'}
            for page,spec in PAGES.items() for i,metric in enumerate(spec['metrics'])]
    tables={'lineage':'gold_source_coverage','metrics':'gold_kpi_dictionary',
            'readiness':'use_case_readiness' if store.layer_enabled('use_cases') else 'gold_use_case_readiness'}
    if kind not in tables:raise DataError('Unknown metadata view.',404)
    return [{key:normalize_json(value) for key,value in row.items()} for row in
            store.query(f'SELECT * FROM {store.table(tables[kind])} LIMIT 2000',{},user)]


@app.get("/api/schema/{name}")
def table_schema(name: str, user: Viewer = Depends(viewer), layer: Literal["gold","use_cases"] = "gold"):
    require_table(name,user,layer)
    return {"name":name,"source":store.source_label(name,layer),"schema":store.columns(name,user,layer)}


@app.get("/api/connection")
def connection_settings(user: Viewer = Depends(viewer)):
    return {"mode":store.mode,"connection":store.connection()}


@app.post("/api/connection")
def connect(settings:ConnectionSettings, user: Viewer = Depends(viewer)):
    if store.mode!='live':
        raise DataError('Sample mode uses local reference data. Connect live sources after deployment.',400)
    profile=settings.profile()
    token=ACTIVE_CONNECTION.set(profile)
    try:
        try:store.query('SELECT 1 AS connection_ok',{},user)
        except DataError as error:
            raise DataError('Warehouse/API connection failed before any source was read: '+str(error),error.status) from error
        verified={}
        for layer in ['gold','use_cases']:
            if not store.layer_enabled(layer):continue
            try:verified[layer]=len(table_catalog(user,layer))
            except DataError as error:
                raise DataError(f'{layer} source metadata access failed: '+str(error),error.status) from error
        response=JSONResponse({'status':'connected','connection':profile,'verified_source_objects':verified,
            'verification':'Warehouse and selected publication metadata verified. Data permissions and columns are checked per visual.'})
        response.set_cookie('marketing_connection',json.dumps(profile),httponly=True,secure=True,samesite='lax',max_age=2592000)
        return response
    finally:ACTIVE_CONNECTION.reset(token)


@app.get("/api/workspace-schema")
def workspace_schema(user: Viewer = Depends(viewer)):
    if store.mode=="preview":
        return {"verification":"UPLOADED_SCHEMA_REFERENCE","tables":[t for t in WORKSPACE_CONTRACT['tables'].values()
            if store.layer_enabled('use_cases' if t['schema']=='usecases' else 'gold')]}
    locations={store.catalog:{"bronze","silver","model",store.schema}} if store.layer_enabled("gold") else {}
    if store.layer_enabled("use_cases"):locations.setdefault(store.use_cases_catalog,set()).add(store.use_cases_schema)
    tables={}
    for catalog,schemas in locations.items():
        params={f"schema{i}":schema for i,schema in enumerate(sorted(schemas))}
        names=", ".join(":"+name for name in params)
        safe_catalog="`"+catalog.replace("`","``")+"`"
        rows=store.query(f"SELECT table_catalog, table_schema, table_name, column_name, full_data_type FROM {safe_catalog}.information_schema.columns "
            f"WHERE table_schema IN ({names}) ORDER BY table_schema, table_name, ordinal_position",params,user)
        for row in rows:
            key=(row['table_catalog'],row['table_schema'],row['table_name'])
            entry=tables.setdefault(key,{'catalog':key[0],'schema':key[1],'name':key[2],'columns':[]})
            entry['columns'].append({'name':row['column_name'],'type':row['full_data_type']})
    return {"verification":"LIVE_AUTHORIZED_INFORMATION_SCHEMA","tables":list(tables.values())}


class GenieQuestion(BaseModel):
    question:str=Field(min_length=1,max_length=4000)
    conversation_id:str=''
    conversation_key:str=''


@app.get('/api/genie/config')
def genie_config(user:Viewer=Depends(viewer)):
    import os
    return {'mode':store.mode,'configured':bool(os.getenv('GENIE_SPACE_ID')),'space_id':os.getenv('GENIE_SPACE_ID',''),
        'examples':genie.EXAMPLES,'dashboard_filters_apply':False}


@app.post('/api/genie/messages')
def genie_send(body:GenieQuestion,user:Viewer=Depends(viewer)):
    if not body.question.strip():raise DataError('Enter a question.',400)
    if store.mode=='preview':return genie.sample(store,user,body.question.strip())
    return genie.send(store,user,body.question.strip(),body.conversation_id,body.conversation_key)


@app.get('/api/genie/messages/{conversation}/{message_id}')
def genie_poll(conversation:str,message_id:str,key:str=Query('',max_length=128),user:Viewer=Depends(viewer)):
    if store.mode!='live':raise DataError('Live Genie polling is unavailable in sample mode.',400)
    return genie.poll(store,user,conversation,message_id,key)


DIST = APP_ROOT / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise DataError("Unknown API endpoint.", 404)
    index = DIST / "index.html"
    if not index.exists():
        raise DataError("Build the frontend with npm run build before starting the app.")
    return FileResponse(index)
