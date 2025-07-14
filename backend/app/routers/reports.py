from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import defaultdict
from app.supabase.client import supabase
from dateutil.parser import isoparse
from fastapi import APIRouter, Query, HTTPException, Response
from datetime import datetime, date, timezone, time, timedelta
from dateutil.parser import isoparse
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from app.services.pdf_service import ReportsService
import io

router = APIRouter(prefix="/reports", tags=["Reports"])


def build_windows(period: str, count: int):
    """
    Returns a list of (start_date: date, end_date: date) tuples,
    oldest→newest, each covering the 26th→25th monthly window.
    """
    return [
        tuple(map(parse_date, get_period_range(period, offset)))
        for offset in range(count - 1, -1, -1)
    ]


def get_period_range(month_year: str, offset: int = 0):
    """
    Returns (start_iso, end_iso) for a custom monthly window: 26th to 25th.
    """
    base = datetime.strptime(
        f"01-{month_year}", "%d-%m-%Y") - relativedelta(months=1)
    adjusted = base - relativedelta(months=offset)
    start = adjusted.replace(day=26)
    end = (start + relativedelta(months=1)).replace(day=25)
    return start.date().isoformat(), end.date().isoformat()


def parse_date(date_str: str) -> date:
    """
    Parses an ISO-formatted date string into a date object.

    Raises HTTPException(400) on invalid format.
    """
    try:
        return isoparse(date_str).astimezone(timezone.utc).date()
    except Exception:
        raise HTTPException(400, detail=f"Invalid date format: {date_str}")


def get_cutoff_windows(month_year: str, num_periods: int):
    """
    Returns a list of (start_date, end_date) as date objects,
    where each window runs 26th → 25th, oldest first.
    """
    # Build the “anchor” on the 25th of the requested MM-YYYY
    anchor = datetime.strptime(f"25-{month_year}", "%d-%m-%Y").date()
    windows = []
    for i in reversed(range(num_periods)):
        # Move back i months
        end = (anchor - relativedelta(months=i))
        start = (end - relativedelta(months=1)) + relativedelta(days=1)
        # Now start is the 26th of the previous month, end is the 25th
        windows.append((start, end))
    return windows


def fetch_all_entries(query):
    """
    Helper to page through Supabase results in 1 000-row batches
    until no more rows are returned.
    """
    all_rows = []
    page = 0
    page_size = 1000

    while True:
        start = page * page_size
        end = start + page_size - 1
        batch = query.range(start, end).execute().data or []
        if not batch:
            break
        all_rows.extend(batch)
        page += 1

    return all_rows


@router.get("/company-usage")
def company_usage_report(
    company_id: int = Query(...),
    period: str = Query(...),
    months: int = Query(6),
    include_logs: bool = Query(True),
    entry_type: str = Query(None, description="Optional entry_type filter"),
    exclude_tag: str = Query(None, description="Optional tag to exclude")
):
    try:
        # 1) Build windows in oldest→newest order
        periods = build_windows(period, months)

        # 2) Use the correct min/max from oldest start → newest end
        min_date = periods[0][0]
        max_date = periods[-1][1]

        # 3) Fetch entries
        min_ts = datetime.combine(periods[0][0], time(
            0, 0), tzinfo=timezone.utc).isoformat()
        max_ts = datetime.combine(periods[-1][1] + timedelta(days=1),
                                  time(0, 0), tzinfo=timezone.utc).isoformat()
        query = (
            supabase
            .table("time_entries")
            .select("id, hours, start_time")
            .eq("company_hubspot_id", company_id)
            .gte("start_time", min_date)
            .lte("start_time", max_date)
            .neq("tag", exclude_tag)
            .gte("start_time", min_ts)
            .lt("start_time", max_ts)
        )
        if entry_type:
            query = query.eq("entry_type", entry_type)
        entries = query.execute().data or []

        # 4) Bucket into each window
        period_totals = [0.0] * months
        period_logs = [[] for _ in range(months)]

        for entry in entries:
            dt = isoparse(entry["start_time"]).astimezone(timezone.utc).date()
            for i, (start, end) in enumerate(periods):
                if start <= dt <= end:
                    period_totals[i] += float(entry["hours"] or 0)
                    period_logs[i].append(entry["id"])
                    break

        # 5) Fetch SLA and compute metrics
        sla_res = (
            supabase
            .table("hubspot_companies")
            .select("hours_per_month")
            .eq("hubspot_id", company_id)
            .limit(1)
            .execute()
        )
        sla = float(sla_res.data[0].get(
            "hours_per_month") or 0) if sla_res.data else 0
        total = sum(period_totals)
        average = total / months
        percentage_usage = (total / (sla * months)) * 100 if sla > 0 else None

        # 6) Return aligned data (no duplicate keys, no extra reversals)
        return {
            "company_id": company_id,
            "months": months,
            "periods": [(s.isoformat(), e.isoformat()) for s, e in periods],
            "total_time": total,
            "period_totals": period_totals,   # oldest→newest
            "sla": sla,
            "average": average,
            "percentage_usage": percentage_usage,
            "missing_sla": sla == 0,
            "current_period_logs": period_logs[0] if include_logs else []
        }

    except Exception as e:
        return {"detail": str(e)}


@router.get("/all-company-usage")
def all_company_usage_report(
    period: str = Query(...),
    months: int = Query(6),
    exclude_tag: str = Query(None, description="Optional tag to exclude"),
    entry_type: str = Query(None, description="Optional entry_type filter")
):
    try:
        periods = [get_period_range(period, i) for i in range(months)]
        min_date, max_date = periods[-1][0], periods[0][1]

        query = supabase.table("time_entries").select(
            "id, hours, company_hubspot_id, start_time"
        ).gte("start_time", min_date).lte("start_time", max_date).neq("tag", exclude_tag)
        if entry_type:
            query = query.eq("entry_type", entry_type)
        entries = query.execute().data or []

        company_usage = defaultdict(lambda: {
            "period_totals": [0.0] * months,
            "time_log_ids": [[] for _ in range(months)]
        })

        for entry in entries:
            cid = entry.get("company_hubspot_id")
            if not cid:
                continue
            dt = datetime.fromisoformat(
                entry["start_time"]).replace(tzinfo=None)
            for i, (start_str, end_str) in enumerate(periods):
                if datetime.fromisoformat(start_str) <= dt <= datetime.fromisoformat(end_str):
                    hours = float(entry.get("hours") or 0)
                    company_usage[cid]["period_totals"][i] += hours
                    company_usage[cid]["time_log_ids"][i].append(entry["id"])
                    break

        company_ids = list(company_usage.keys())
        if not company_ids:
            return []

        company_res = supabase.table("hubspot_companies").select(
            "hubspot_id, hours_per_month, raw"
        ).in_("hubspot_id", company_ids).execute()
        company_meta = {c["hubspot_id"]: c for c in company_res.data or []}

        result = []
        for cid, data in company_usage.items():
            meta = company_meta.get(cid, {})
            sla = float(meta.get("hours_per_month") or 0)
            total = sum(data["period_totals"])
            average = total / months
            percentage_usage = (total / (sla * months)) * \
                100 if sla > 0 else None

            result.append({
                "company_id": cid,
                "sla": sla,
                "months": months,
                "periods": periods,
                "total_time": total,
                "period_totals": data["period_totals"],
                "average": average,
                "percentage_usage": percentage_usage,
                "missing_sla": sla == 0,
                "company_raw": meta.get("raw"),
                "time_logs": data["time_log_ids"][0]
            })

        return result

    except Exception as e:
        return {"detail": str(e)}


@router.get(
    "/companies-with-time",
    summary="Fetch companies with time entries in a date range",
    description="""
    Returns companies that have logged time entries between `start_date` and `end_date`.

    - `start_date` and `end_date` must be valid ISO date strings (e.g. "2025-07-01").
    - `min_hours`: filter out companies whose total hours are below this threshold.
    - `include_company_data`: when true, fetches each company's `raw` metadata and SLA hours.
    - Optional filters: `entry_type`, `exclude_tag`.

    The response for each company includes:
      - company_id
      - total_hours (rounded to 2 decimals)
      - entry_count
      - percentage_usage against SLA (if available)
      - missing_sla flag
      - sla (hours_per_month)
      - time_entry_ids
      - company_raw metadata (if requested)
    """
)
def companies_with_time_entries(
    start_date: str = Query(..., description="Start date (ISO, inclusive)"),
    end_date: str = Query(..., description="End date (ISO, inclusive)"),
    min_hours: float = Query(
        0.0, ge=0.0, description="Minimum total hours to include"),
    include_company_data: bool = Query(
        True, description="Whether to include company metadata"),
    entry_type: str = Query(None, description="Optional entry_type filter"),
    exclude_tag: str = Query(None, description="Optional tag to exclude")
):
    """
    Endpoint that returns all companies with time entries in the specified date range,
    aggregated by company, and filtered by minimum hours and optional tags or types.

    Raises HTTPException(400) if date parsing fails.
    """
    # 1) Validate and parse dates
    start_dt = parse_date(start_date)
    end_dt = parse_date(end_date)
    if end_dt < start_dt:
        raise HTTPException(
            400, detail="end_date must be on or after start_date")

    # 2) Build and execute time_entries query
    q = (
        supabase
        .table("time_entries")
        .select("id, hours, company_hubspot_id, start_time")
        .gte("start_time", start_dt.isoformat())
        .lte("start_time", end_dt.isoformat())
    )
    if exclude_tag:
        q = q.neq("tag", exclude_tag)
    if entry_type:
        q = q.eq("entry_type", entry_type)

    entries = q.execute().data or []

    # 3) Aggregate by company
    grouped = defaultdict(
        lambda: {"time_entry_ids": [], "total_hours": 0.0, "entry_count": 0})
    for entry in entries:
        cid = entry.get("company_hubspot_id")
        if not cid:
            continue
        hours = float(entry.get("hours") or 0)
        grouped[cid]["time_entry_ids"].append(entry["id"])
        grouped[cid]["total_hours"] += hours
        grouped[cid]["entry_count"] += 1

    # 4) Optionally load company metadata
    company_map = {}
    if include_company_data and grouped:
        company_ids = list(grouped.keys())
        res = (
            supabase
            .table("hubspot_companies")
            .select("hubspot_id, raw, hours_per_month")
            .in_("hubspot_id", company_ids)
            .execute()
        )
        for c in res.data or []:
            company_map[int(c["hubspot_id"])] = {
                "raw": c.get("raw", {}),
                "sla": float(c.get("hours_per_month") or 0)
            }

    # 5) Build result list
    result = []
    for cid, data in grouped.items():
        total = data["total_hours"]
        if total < min_hours:
            continue

        meta = company_map.get(cid, {})
        sla = meta.get("sla", 0)
        pct = (total / sla * 100) if sla > 0 else None

        result.append({
            "company_id": cid,
            "total_hours": round(total, 2),
            "entry_count": data["entry_count"],
            "percentage_usage": pct,
            "missing_sla": sla == 0,
            "sla": sla,
            "time_entry_ids": data["time_entry_ids"],
            "company_raw": meta.get("raw") if include_company_data else None
        })

    return result


# @router.get("/over-sla")
# def companies_over_sla(
#     period: str = Query(...),
#     num_periods: int = Query(1, ge=1, le=12),
#     entry_type: str = Query(None),
#     exclude_tag: str = Query(None, description="Optional tag to exclude")
# ):
#     try:
#         periods = [get_period_range(period, i) for i in range(num_periods)]
#         min_date = periods[-1][0]
#         max_date = periods[0][1]

#         print(
#             f"[DEBUG] SLA REPORT for {num_periods} period(s) from {min_date} to {max_date}")
#         for i, (start, end) in enumerate(periods):
#             print(f"  - Period {i+1}: {start} to {end}")

#         customer_res = supabase.table("hubspot_companies").select(
#             "hubspot_id, hours_per_month, lifecycle_stage, raw"
#         ).ilike("lifecycle_stage", "customer").execute()
#         customers = customer_res.data or []
#         customer_ids = [c["hubspot_id"] for c in customers]
#         print(f"[DEBUG] Found {len(customer_ids)} customer companies")

#         company_meta = {
#             c["hubspot_id"]: {
#                 "sla": float(c.get("hours_per_month") or 0),
#                 "raw": c.get("raw", {})
#             }
#             for c in customers
#         }

#         query = supabase.table("time_entries").select(
#             "id, hours, company_hubspot_id, start_time"
#         ).in_("company_hubspot_id", customer_ids).gte("start_time", min_date).lte("start_time", max_date).neq("tag", exclude_tag)
#         if entry_type:
#             query = query.eq("entry_type", entry_type)
#         entries = query.execute().data or []

#         usage_by_company = defaultdict(lambda: [0.0] * num_periods)
#         for entry in entries:
#             cid = entry.get("company_hubspot_id")
#             if not cid or not entry.get("start_time"):
#                 continue
#             dt = datetime.fromisoformat(
#                 entry["start_time"]).replace(tzinfo=None)
#             for i, (start_str, end_str) in enumerate(periods):
#                 if datetime.fromisoformat(start_str) <= dt <= datetime.fromisoformat(end_str):
#                     usage_by_company[cid][i] += float(entry.get("hours") or 0)
#                     break

#         now = datetime.strptime(f"01-{period}", "%d-%m-%Y")

#         def get_total_hours(since_months: int, company_id: int):
#             start_date = (now - relativedelta(months=since_months)
#                           ).replace(day=26).date().isoformat()
#             q = supabase.table("time_entries").select(
#                 "hours").eq("company_hubspot_id", company_id).neq("tag", exclude_tag)
#             if entry_type:
#                 q = q.eq("entry_type", entry_type)
#             return sum(float(e["hours"] or 0) for e in q.gte("start_time", start_date).lte("start_time", max_date).execute().data or [])

#         result = []
#         for cid in customer_ids:
#             sla = company_meta[cid]["sla"]
#             period_usage = usage_by_company.get(cid, [0.0] * num_periods)
#             total = sum(period_usage)
#             average = total / num_periods
#             percentage_usage = (average / sla * 100) if sla > 0 else None
#             over_sla = percentage_usage and percentage_usage > 100

#             if total > 0:
#                 print(f"\n[DEBUG] Company {cid}")
#                 print(f"  - SLA: {sla}")
#                 print(f"  - Period usage: {period_usage}")
#                 print(f"  - Total: {total}")
#                 print(f"  - Average: {average}")
#                 print(f"  - % Usage: {percentage_usage}")
#                 print(f"  - Over SLA? {'Yes' if over_sla else 'No'}")

#             last_6mo_usage = get_total_hours(6, cid)
#             last_12mo_usage = get_total_hours(12, cid)

#             if over_sla:
#                 result.append({
#                     "company_id": cid,
#                     "sla": sla,
#                     "periods": periods,
#                     "period_usage": period_usage,
#                     "total_usage": total,
#                     "average_usage": average,
#                     "percentage_usage": percentage_usage,
#                     "over_sla": over_sla,
#                     "last_6_months_usage": last_6mo_usage,
#                     "last_12_months_usage": last_12mo_usage,
#                     "missing_sla": sla == 0,
#                     "company_raw": company_meta[cid]["raw"]
#                 })

#         print(f"\n[DEBUG] Final count of over-SLA companies: {len(result)}")
#         return result

#     except Exception as e:
#         print(f"[ERROR] Exception in /over-sla report: {e}")
#         return {"detail": str(e)}

@router.get(
    "/over-sla",
    summary="List companies whose average or monthly usage exceeds SLA",
)
def companies_over_sla(
    period: str = Query(..., description="MM-YYYY, e.g. '06-2025'"),
    num_periods: int = Query(6, ge=1, le=12),
    filter_monthly: bool = Query(
        False, description="Include companies with any single month over SLA"),
    entry_type: str = Query(None, description="Optional entry_type filter"),
    exclude_tag: str = Query(None, description="Optional tag to exclude")
):
    # 1) Build rolling windows
    windows = []
    try:
        for offset in range(num_periods - 1, -1, -1):
            start_iso, end_iso = get_period_range(period, offset)
            windows.append((parse_date(start_iso), parse_date(end_iso)))
    except HTTPException:
        raise HTTPException(
            400, detail="Invalid period format; expected MM-YYYY")
    oldest_date, newest_date = windows[0][0], windows[-1][1]

    oldest_ts = datetime.combine(oldest_date, time(
        0, 0), tzinfo=timezone.utc).isoformat()
    next_day_ts = datetime.combine(
        newest_date + timedelta(days=1), time(0, 0), tzinfo=timezone.utc).isoformat()

    # 2) Fetch customer companies
    cust_res = (
        supabase
        .table("hubspot_companies")
        .select("hubspot_id, hours_per_month, raw")
        .ilike("lifecycle_stage", "customer")
        .execute()
    )
    customers = cust_res.data or []
    if not customers:
        return []

    meta = {int(c["hubspot_id"]): {"sla": float(
        c.get("hours_per_month") or 0), "raw": c.get("raw", {})} for c in customers}
    customer_ids = list(meta.keys())

    # 3) Fetch entries
    base_query = (
        supabase
        .table("time_entries")
        .select("company_hubspot_id, hours, start_time")
        .in_("company_hubspot_id", customer_ids)
        .gte("start_time", oldest_ts)
        .lt("start_time", next_day_ts)
    )
    if exclude_tag:
        base_query = base_query.neq("tag", exclude_tag)
    if entry_type:
        base_query = base_query.eq("entry_type", entry_type)

    entries = fetch_all_entries(base_query)

    # 4) Bucket and rolling totals
    usage_by_company = defaultdict(lambda: [0.0] * num_periods)
    roll_6 = defaultdict(float)
    roll_12 = defaultdict(float)
    six_cutoff = newest_date - relativedelta(months=6)
    twelve_cutoff = newest_date - relativedelta(months=12)

    for e in entries:
        cid = int(e.get("company_hubspot_id", 0))
        if cid not in meta or not e.get("start_time"):
            continue
        dt = isoparse(e["start_time"]).astimezone(timezone.utc).date()
        hrs = float(e.get("hours") or 0)

        for idx, (start, end) in enumerate(windows):
            if start <= dt <= end:
                usage_by_company[cid][idx] += hrs
                break

        if dt >= six_cutoff:
            roll_6[cid] += hrs
        if dt >= twelve_cutoff:
            roll_12[cid] += hrs

    # 5) Build response
    result = []
    for cid, usage_list in usage_by_company.items():
        sla = meta[cid]["sla"]
        total_usage = sum(usage_list)
        avg_usage = total_usage / num_periods
        pct_usage = (avg_usage / sla * 100) if sla > 0 else None
        monthly_exceed = any(u > sla for u in usage_list)
        latest_usage = usage_list[-1]

        if filter_monthly:
            if not monthly_exceed:
                continue
        else:
            if not pct_usage or pct_usage <= 100:
                continue
            if latest_usage <= 0:
                continue

        result.append({
            "company_id": cid,
            "sla": sla,
            "periods": [(s.isoformat(), e.isoformat()) for s, e in windows],
            "period_usage": usage_list,
            "total_usage": total_usage,
            "average_usage": avg_usage,
            "percentage_usage": pct_usage,
            "last_6_months_usage": roll_6[cid],
            "last_12_months_usage": roll_12[cid],
            "missing_sla": sla == 0,
            "company_raw": meta[cid]["raw"]
        })

    return result


@router.get("/pdf/{company_id}", summary="Download PDF report for a company")
def company_report_pdf(
    company_id: int,
    period: str = Query("06-2025", description="MM-YYYY"),
    months: int = Query(6, ge=1, le=12),
    exclude_tag: str = Query(None, description="Optional tag to exclude"),
    entry_type: str = Query(None, description="Optional entry_type filter"),
    entry_neq: str = Query(
        None, description="Optional entry_type to exclude, secondary to entry_type")
):
    try:
        data = ReportsService.get_company_usage(
            company_id=company_id,
            period=period,
            months=months,
            exclude_tag=exclude_tag,
            entry_type=entry_type,
            entry_neq=entry_neq
        )
        pdf_bytes = ReportsService.build_pdf(data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=company_{company_id}_report.pdf"
            }
        )
    except ValueError as ve:
        raise HTTPException(404, str(ve))
    except Exception as e:
        raise HTTPException(500, f"Error generating PDF: {e}")
