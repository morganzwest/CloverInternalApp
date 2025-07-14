import io
import base64
from datetime import datetime, time, timedelta, timezone
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from jinja2 import Environment, FileSystemLoader, select_autoescape
from xhtml2pdf import pisa

from app.supabase.client import supabase   # adjust import path if needed


class ReportsService:
    @staticmethod
    def get_company_usage(company_id: int, period: str, months: int, exclude_tag: str = None, entry_type: str = None):
        """
        Fetches and buckets time entries for the given company over the requested periods.
        Returns a dict with:
          - company_raw
          - total_time (float)
          - daily_totals: { 'YYYY-MM-DD': hours }
          - entries: [ {id, date, hours, description}, ... ]
        """
        # 1) Build the date windows (26th→25th) and overall range
        windows = []
        for offset in range(months - 1, -1, -1):
            # get_period_range exactly as in your router
            start_iso, end_iso = ReportsService.get_period_range(
                period, offset)
            windows.append((isoparse(start_iso).date(),
                           isoparse(end_iso).date()))
        oldest_date, newest_date = windows[0][0], windows[-1][1]

        oldest_ts = datetime.combine(oldest_date, time(
            0, 0), tzinfo=timezone.utc).isoformat()
        next_day = newest_date + timedelta(days=1)
        next_day_ts = datetime.combine(next_day, time(
            0, 0), tzinfo=timezone.utc).isoformat()

        # 2) Fetch company SLA + raw
        comp = supabase.table("hubspot_companies") \
                       .select("hubspot_id, hours_per_month, raw") \
                       .eq("hubspot_id", company_id) \
                       .limit(1) \
                       .execute().data
        if not comp:
            raise ValueError(f"Company {company_id} not found")
        sla = float(comp[0].get("hours_per_month") or 0)
        company_raw = comp[0].get("raw", {})

        # 3) Fetch all time_entries paged
        base_q = supabase.table("time_entries") \
                         .select("id, hours, start_time, description") \
                         .eq("company_hubspot_id", company_id) \
                         .gte("start_time", oldest_ts) \
                         .lt("start_time", next_day_ts) \
                         .neq("tag", "Allowable travel time")
        if exclude_tag:
            base_q = base_q.neq("tag", exclude_tag)
        if entry_type:
            base_q = base_q.eq("entry_type", entry_type)

        entries = ReportsService._fetch_all_entries(base_q)

        # 4) Bucket into daily totals and assemble rows
        daily_totals = defaultdict(float)
        entry_rows = []

        for e in entries:
            dt = isoparse(e["start_time"]).astimezone(
                timezone.utc).date().isoformat()
            hrs = float(e.get("hours") or 0)
            desc = e.get("description", "")
            daily_totals[dt] += hrs
            entry_rows.append({
                "id": e["id"],
                "date": dt,
                "hours": hrs,
                "description": desc
            })

        total_time = sum(daily_totals.values())
        entry_rows.sort(key=lambda r: r["date"])

        windows = []
        for offset in range(months - 1, -1, -1):
            s, e = ReportsService.get_period_range(period, offset)
            windows.append((s, e))

        return {
            "company_raw": company_raw,
            "sla": sla,
            "total_time": total_time,
            "daily_totals": dict(daily_totals),
            "entries": entry_rows,
            "windows": windows,    # ← new
            "period": period,      # ← handy if you want just “06-2025”
            "months": months,
        }

    @staticmethod
    def build_pdf(data: dict) -> bytes:
        # unpack your date‐range (assumes you returned these in get_company_usage)
        windows = data["windows"]       # list of (start_iso, end_iso) strings
        oldest_iso = windows[0][0]
        newest_iso = windows[-1][1]
        oldest_dt = isoparse(oldest_iso).date()
        newest_dt = isoparse(newest_iso).date()

        # 1) make a bar chart with all dates in range
        daily = data["daily_totals"]
        # build full date sequence:
        all_dates = []
        d = oldest_dt
        while d <= newest_dt:
            all_dates.append(d)
            d += timedelta(days=1)

        # map to hours (default 0)
        hours = [daily.get(d.isoformat(), 0) for d in all_dates]

        fig, ax = plt.subplots(figsize=(8, 3))
        ax.bar(all_dates, hours, width=0.8)

        # format x axis
        ax.set_xlim(oldest_dt, newest_dt)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=7))
        plt.setp(ax.get_xticklabels(), rotation=30, ha='right')

        ax.set_title("Time Delivered by Day")
        ax.set_ylabel("Hours")
        fig.tight_layout()

        # save to PNG buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        chart_b64 = base64.b64encode(buf.read()).decode()

        # 2) render HTML
        env = Environment(
            loader=FileSystemLoader("app/templates"),
            autoescape=select_autoescape(["html", "xml"])
        )
        tmpl = env.get_template("company_report.html")
        html = tmpl.render(
            company=data["company_raw"],
            total_time=data["total_time"],
            chart_png=chart_b64,
            entries=data["entries"],
            windows=data["windows"]
        )

        # 3) HTML → PDF
        pdf_buf = io.BytesIO()
        status = pisa.CreatePDF(src=html, dest=pdf_buf)
        if status.err:
            raise RuntimeError("Failed to generate PDF")
        return pdf_buf.getvalue()

    @staticmethod
    def _fetch_all_entries(query):
        """Page through Supabase in 1,000-row slices."""
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

    @staticmethod
    def get_period_range(month_year: str, offset: int = 0):
        """Helper to compute 26th→25th windows in ISO date strings."""
        base = datetime.strptime(
            f"01-{month_year}", "%d-%m-%Y") - relativedelta(months=1)
        adj = base - relativedelta(months=offset)
        start = adj.replace(day=26)
        end = (start + relativedelta(months=1)).replace(day=25)
        return start.date().isoformat(), end.date().isoformat()
