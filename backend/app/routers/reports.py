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
from pydantic import Field, BaseModel
from httpx import RemoteProtocolError
from typing import Optional, List, Dict
from app.services.hubspot import fetch_all_users, map_owner_ids_to_users

router = APIRouter(prefix="/reports", tags=["Reports"])

class EmployeePayroll(BaseModel):
    owner_id: int = Field(..., description="ID of the time‑entry owner")
    totalTime: float = Field(
        ..., description="Total hours logged in the period"
    )
    expenses: float = Field(
        0.0, description="Total expenses (placeholder, always 0 for now)"
    )
    contracted: float = Field(
        0.0, description="Contracted hours (placeholder, always 0 for now)"
    )


def get_period_range(month_year: str, offset: int = 0):
    """
    Returns (start_iso, end_iso) for a custom monthly window: 
    26th 00:00:00 → 25th 23:59:59 UTC.
    """
    # Anchor on the 1st of MM-YYYY, back one month + offset
    anchor = datetime.strptime(f"01-{month_year}", "%d-%m-%Y")
    base = anchor - relativedelta(months=1 + offset)
    # Start on the 26th at 00:00 UTC
    start = base.replace(day=26, hour=0, minute=0,
                         second=0, tzinfo=timezone.utc)
    # End on the *next* month’s 25th at 23:59:59 UTC
    end = (start + relativedelta(months=1)).replace(day=25,
                                                    hour=23,
                                                    minute=59,
                                                    second=59)
    return start.isoformat(), end.isoformat()


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


def fetch_all_entries(base_query, order_column="id"):
    all_rows, offset, page_size = [], 0, 1000

    while True:
        q = (
            base_query
            .order(order_column, desc=False)
            .range(offset, offset + page_size - 1)
        )
        try:
            batch = q.execute().data or []
        except RemoteProtocolError:
            # cut the page size in half and retry
            page_size = max(10, page_size // 2)
            continue

        if not batch:
            break

        all_rows.extend(batch)
        offset += page_size

    return all_rows


@router.get("/company-usage")
def company_usage_report(
    company_id: int = Query(...),
    period: str = Query(...),
    months: int = Query(6),
    include_logs: bool = Query(True),
    entry_type: Optional[str] = Query(
        None, description="Optional entry_type filter"),
    exclude_tag: Optional[str] = Query(
        None, description="Optional tag to exclude")
):
    """
    Returns usage for a single company over N rolling windows of 26th→25th.
    """
    try:
        # 1) build the per‐month windows: offset=0 is the current 26→25 window
        periods = [get_period_range(period, i) for i in range(months)]
        # periods[0] = most recent 26→25, periods[-1] = oldest

        # 2) fetch *all* entries across all windows:
        # oldest window start (e.g. 2024-12-26T00:00:00Z)
        overall_start, _ = periods[-1]
        # most recent window end (e.g. 2025-06-25T23:59:59Z)
        _, overall_end = periods[0]

        query = (
            supabase.table("time_entries")
            .select("id, hours, start_time")
            .eq("company_hubspot_id", company_id)
            .gte("start_time", overall_start)
            .lte("start_time", overall_end)
            .neq("tag", exclude_tag)
        )
        if entry_type:
            query = query.eq("entry_type", entry_type)

        entries = query.execute().data or []

        # 3) bucket them into each window
        period_totals = [0.0] * months
        period_logs = [[] for _ in range(months)]

        for entry in entries:
            dt = isoparse(entry["start_time"])
            hrs = float(entry.get("hours") or 0)

            for idx, (start_iso, end_iso) in enumerate(periods):
                start = isoparse(start_iso)
                end = isoparse(end_iso)
                if start <= dt <= end:
                    period_totals[idx] += hrs
                    period_logs[idx].append(entry["id"])
                    break

        # 4) SLA & stats
        sla_res = (
            supabase.table("hubspot_companies")
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

        return {
            "company_id": company_id,
            "months": months,
            "periods": periods,
            "total_time": total,
            "period_totals": period_totals,
            "sla": sla,
            "average": average,
            "percentage_usage": percentage_usage,
            "missing_sla": sla == 0,
            "current_period_logs": period_logs[0] if include_logs else []
        }

    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/time-entry-detail", summary="Fetch full rows for a list of time-entry IDs")
def time_entry_detail(
    ids: List[str] = Query(..., alias="ids[]",
                           description="Array of time_entry IDs")
):
    """
    Given ?ids[]=uuid1&ids[]=uuid2… returns the full time_entries rows
    for each matching id.
    """
    res = (
        supabase
        .table("time_entries")
        .select("*")
        .in_("id", ids)
        .execute()
    )
    return res.data or []


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
        .lte("end_time", end_dt.isoformat())
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
        False, description="Include companies with any single month over SLA"
    ),
    entry_type: Optional[str] = Query(
        None, description="Optional entry_type filter"),
    exclude_tag: Optional[str] = Query(
        None, description="Optional tag to exclude"),
):
    # 1) Build N windows of (start_iso, end_iso) from oldest→newest
    try:
        windows = [
            get_period_range(period, offset)
            for offset in range(num_periods - 1, -1, -1)
        ]
    except Exception:
        raise HTTPException(
            400, detail="Invalid period format; expected MM-YYYY")

    # Extract global query bounds
    oldest_start_iso, _ = windows[0]
    _, newest_end_iso = windows[-1]

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

    # Build metadata map: {company_id: {sla, raw}}
    meta = {
        int(c["hubspot_id"]): {
            "sla": float(c.get("hours_per_month") or 0),
            "raw": c.get("raw", {})
        }
        for c in customers
    }
    customer_ids = list(meta.keys())

    # 3) Fetch all relevant time entries, paged, ordered by id
    base_query = (
        supabase
        .table("time_entries")
        .select("company_hubspot_id, hours, start_time")
        .in_("company_hubspot_id", customer_ids)
        .gte("start_time", oldest_start_iso)
        .lte("start_time", newest_end_iso)
    )
    if exclude_tag:
        base_query = base_query.neq("tag", exclude_tag)
    if entry_type:
        base_query = base_query.eq("entry_type", entry_type)

    entries = fetch_all_entries(base_query, order_column="id")

    # 4) Bucket per company per window, and rolling totals
    usage_by_company = defaultdict(lambda: [0.0] * num_periods)
    roll_6 = defaultdict(float)
    roll_12 = defaultdict(float)

    newest_end_date = isoparse(newest_end_iso).astimezone(timezone.utc).date()
    six_cutoff = newest_end_date - relativedelta(months=6)
    twelve_cutoff = newest_end_date - relativedelta(months=12)

    for e in entries:
        cid = int(e.get("company_hubspot_id", 0))
        if cid not in meta or not e.get("start_time"):
            continue

        dt_utc = isoparse(e["start_time"]).astimezone(timezone.utc)
        hrs = float(e.get("hours") or 0)

        # assign to the correct monthly bucket
        for idx, (start_iso, end_iso) in enumerate(windows):
            start_dt = isoparse(start_iso)
            end_dt = isoparse(end_iso)
            if start_dt <= dt_utc <= end_dt:
                usage_by_company[cid][idx] += hrs
                break

        # rolling sums
        dt_date = dt_utc.date()
        if dt_date >= six_cutoff:
            roll_6[cid] += hrs
        if dt_date >= twelve_cutoff:
            roll_12[cid] += hrs

    # 5) Build final result list
    result = []
    for cid, usage_list in usage_by_company.items():
        sla = meta[cid]["sla"]
        total_usage = sum(usage_list)
        average_usage = total_usage / num_periods if num_periods else 0
        pct_usage = (average_usage / sla * 100) if sla > 0 else None
        monthly_exceed = any(u > sla for u in usage_list)
        latest_usage = usage_list[-1]

        # apply filter_monthly vs. average‐based
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
            "periods": [(s, e) for s, e in windows],
            "period_usage": usage_list,
            "total_usage": total_usage,
            "average_usage": average_usage,
            "percentage_usage": pct_usage,
            "last_6_months_usage": roll_6[cid],
            "last_12_months_usage": roll_12[cid],
            "missing_sla": sla == 0,
            "company_raw": meta[cid]["raw"],
        })

    return result


@router.get("/pdf/{company_id}", summary="Download PDF report for a company")
def company_report_pdf(
    company_id: int,
    period: str = Query("06-2025", description="MM-YYYY"),
    months: int = Query(6, ge=1, le=12),
    exclude_tag: str = Query(None, description="Optional tag to exclude"),
    entry_type: str = Query(None, description="Optional entry_type filter"),
):
    try:
        data = ReportsService.get_company_usage(
            company_id=company_id,
            period=period,
            months=months,
            exclude_tag=exclude_tag,
            entry_type=entry_type,
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

class User(BaseModel):
    id: int
    email: Optional[str]
    firstName: Optional[str]
    lastName: Optional[str]

class OwnerMeta(BaseModel):
    contracted_hours: float = Field(..., description="Contracted hours per period")
    hourly_rate: Optional[float] = Field(None, description="Standard hourly rate")
    eligible_for_overtime: bool = Field(..., description="Whether owner is eligible for overtime")

class PayrollWithUsers(BaseModel):
    payroll: List[EmployeePayroll]
    users: Dict[int, Optional[User]]
    owners: Dict[int, Optional[OwnerMeta]]

@router.get(
    "/payroll/employees",
    response_model=PayrollWithUsers,
    summary="Total hours per owner in a date range, plus user & owner metadata"
)
def payroll_employees(
    start_date: str = Query(..., description="Start ISO date, inclusive"),
    end_date:   str = Query(..., description="End ISO date, inclusive")
):
    # Validate dates
    start_dt = parse_date(start_date)
    end_dt   = parse_date(end_date)
    if end_dt < start_dt:
        raise HTTPException(400, "`end_date` must be on or after `start_date`")

    # Build an inclusive end‑of‑day timestamp for end_date
    end_of_day = datetime.combine(end_dt, time(23, 59, 59, tzinfo=timezone.utc))

    # 1) Page through ALL matching entries from Supabase
    all_entries = []
    page_size = 100
    offset = 0

    while True:
        batch = (
            supabase
              .table("time_entries")
              .select("owner_id, hours")
              .order("id", desc=False)
              .gte("start_time", start_dt.isoformat())
              .lte("start_time", end_of_day.isoformat())
              .range(offset, offset + page_size - 1)
              .execute()
        ).data or []

        if not batch:
            break

        all_entries.extend(batch)
        offset += page_size

    # 2) Sum hours per owner
    totals = defaultdict(float)
    for e in all_entries:
        oid = e.get("owner_id")
        if oid is not None:
            totals[oid] += float(e.get("hours") or 0)

    payroll_list = [
        EmployeePayroll(owner_id=oid, totalTime=hrs, expenses=0.0, contracted=0.0)
        for oid, hrs in totals.items()
    ]

    owner_ids = list(totals.keys())

    # 3) Fetch users via HubSpot & map to OwnerMeta (unchanged)
    all_users = fetch_all_users()
    raw_user_map = map_owner_ids_to_users(owner_ids, all_users)
    users_map: Dict[int, Optional[User]] = {
        oid: User(
            id=int(u["id"]),
            email=u.get("email"),
            firstName=u.get("firstName"),
            lastName=u.get("lastName")
        ) if u else None
        for oid, u in raw_user_map.items()
    }

    owner_meta_res = (
        supabase
          .table("owners")
          .select("hubspot_id, contracted_hours, hourly_rate, eligible_for_overtime")
          .in_("hubspot_id", owner_ids)
          .execute()
    )
    meta_list = owner_meta_res.data or []
    owner_meta_map = {m["hubspot_id"]: m for m in meta_list}

    owners_map: Dict[int, Optional[OwnerMeta]] = {}
    for oid in owner_ids:
        m = owner_meta_map.get(oid)
        if m:
            owners_map[oid] = OwnerMeta(
                contracted_hours=float(m.get("contracted_hours") or 0),
                hourly_rate=(float(m.get("hourly_rate")) if m.get("hourly_rate") is not None else None),
                eligible_for_overtime=bool(m.get("eligible_for_overtime"))
            )
        else:
            owners_map[oid] = None

    return PayrollWithUsers(
        payroll=payroll_list,
        users=users_map,
        owners=owners_map
    )

class LastSyncResponse(BaseModel):
    last_sync: datetime = Field(
        ..., 
        description="Most recent `last_updated` timestamp from the `time_entries` table (UTC)"
    )

@router.get(
    "/last_sync",
    response_model=LastSyncResponse,
    summary="Get the most recent `last_updated` timestamp from time_entries"
)
def get_last_sync():
    # 1) Fetch the latest last_updated
    res = (
        supabase
        .table("time_entries")
        .select("updated_at")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )

    rows = res.data or []
    if not rows:
        # no entries at all
        raise HTTPException(status_code=404, detail="No time entries found")

    raw_ts = rows[0].get("updated_at")
    if not raw_ts:
        raise HTTPException(status_code=500, detail="Malformed `updated_at` value")

    # 2) Parse & normalize to UTC datetime
    try:
        ts = isoparse(raw_ts).astimezone(timezone.utc)
    except Exception:
        raise HTTPException(status_code=500, detail=f"Invalid timestamp format: {raw_ts}")

    # 3) Return
    return LastSyncResponse(last_sync=ts)
