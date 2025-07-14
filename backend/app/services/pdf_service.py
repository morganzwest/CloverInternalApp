from app.supabase.client import supabase
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from playwright.sync_api import sync_playwright
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import io
import base64
from datetime import timedelta, time, timezone
from dateutil.parser import isoparse
from types import SimpleNamespace
from jinja2 import Environment, FileSystemLoader, select_autoescape
import datetime as dt_module
import logging
import traceback

# force non-GUI rendering
import matplotlib
matplotlib.use('Agg')


class ReportsService:
    @staticmethod
    def get_company_usage(company_id: int, period: str, months: int,
                          exclude_tag: str = None, entry_type: str = None):
        # 1) Build our windows
        windows = []
        for offset in range(months - 1, -1, -1):
            start_iso, end_iso = ReportsService.get_period_range(
                period, offset)
            windows.append((start_iso, end_iso))
        oldest_iso, _ = windows[0]
        _, newest_iso = windows[-1]

        # 2) Fetch SLA & raw
        comp = supabase.table("hubspot_companies") \
                       .select("hubspot_id, hours_per_month, raw") \
                       .eq("hubspot_id", company_id) \
                       .limit(1) \
                       .execute().data
        if not comp:
            raise ValueError(f"Company {company_id} not found")
        sla = float(comp[0].get("hours_per_month") or 0)
        company_raw = comp[0].get("raw", {})

        # 3) Fetch time entries
        oldest_date = isoparse(oldest_iso).date()
        newest_date = isoparse(newest_iso).date()
        oldest_ts = dt_module.datetime.combine(
            oldest_date, time(0, 0), tzinfo=timezone.utc).isoformat()
        next_day_ts = dt_module.datetime.combine(
            newest_date + timedelta(days=1), time(0, 0), tzinfo=timezone.utc).isoformat()

        base_q = supabase.table("time_entries") \
            .select("id, hours, minutes, start_time, end_time, tag, description") \
            .eq("company_hubspot_id", company_id) \
            .gte("start_time", oldest_ts) \
            .lt("start_time", next_day_ts)
        if exclude_tag:
            base_q = base_q.neq("tag", exclude_tag)
        if entry_type:
            base_q = base_q.eq("entry_type", entry_type)

        entries = ReportsService._fetch_all_entries(base_q)

        # 4) Bucket daily totals
        daily_totals = defaultdict(float)
        entry_rows = []
        for e in entries:
            entry_date = isoparse(e["start_time"]).astimezone(
                timezone.utc).date().isoformat()
            hrs = float(e.get("hours") or 0)
            entry_rows.append({
                "id": e["id"],
                "start_time": e["start_time"],
                "end_time": e["end_time"],
                "hours": hrs,
                "tag": e.get("tag", ""),
                "description": e.get("description", "")
            })
            daily_totals[entry_date] += hrs

        total_time = sum(daily_totals.values())
        entry_rows.sort(key=lambda r: r["start_time"])

        # 5) Build monthly totals
        monthly_totals = []
        for start_iso, end_iso in windows:
            # parse start month label
            month_label = dt_module.datetime.fromisoformat(
                end_iso).strftime('%b %Y')
            # sum usage in window
            usage = 0
            cur = dt_module.date.fromisoformat(start_iso)
            end = dt_module.date.fromisoformat(end_iso)
            while cur <= end:
                usage += daily_totals.get(cur.isoformat(), 0)
                cur += timedelta(days=1)
            monthly_totals.append(SimpleNamespace(
                month=month_label, usage=usage))

         # 6) Totals & utilization
        total_usage = sum(m.usage for m in monthly_totals)
        total_sla = sla * months
        total_diff = total_usage - total_sla
        avg_util = (total_usage / total_sla * 100) if total_sla else 0

        return {
            "company_raw": company_raw,
            "sla": sla,
            "total_time": total_time,
            "daily_totals": dict(daily_totals),
            "entries": entry_rows,
            "windows": windows,
            "period": period,
            "months": months,
            "monthly_totals": monthly_totals,
            "total_usage": total_usage,
            "total_sla": total_sla,
            "total_diff": total_diff,
            "avg_util": avg_util,
        }

    @staticmethod
    def build_pdf(data: dict) -> bytes:
        # prepare context
        company = SimpleNamespace(**data["company_raw"])
        entries = [SimpleNamespace(**e) for e in data["entries"]]
        windows = data["windows"]
        sla = data["sla"]
        total_time = data["total_time"]
        monthly_totals = data.get("monthly_totals", [])
        total_usage = data.get("total_usage", 0)
        total_sla = data.get("total_sla", 0)
        total_diff = data.get("total_diff", 0)
        avg_util = data.get("avg_util", 0)

        # build chart with taller aspect
        chart_png = ReportsService._render_chart_png(
            data["daily_totals"], windows)

        # render HTML
        env = Environment(loader=FileSystemLoader(
            "app/templates"), autoescape=select_autoescape(["html", "xml"]))
        tmpl = env.get_template("company_report.html")
        html = tmpl.render(
            company=company,
            sla=sla,
            total_time=total_time,
            chart_png=chart_png,
            entries=entries,
            windows=windows,
            period=data['period'],
            months=data['months'],
            monthly_totals=monthly_totals,
            total_usage=total_usage,
            total_sla=total_sla,
            total_diff=total_diff,
            avg_util=avg_util,
        )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1024, "height": 768})
                page.set_content(html, wait_until="networkidle")
                pdf_bytes = page.pdf(format="A4", print_background=True,
                                     margin={"top": "1cm", "bottom": "1cm", "left": "1cm", "right": "1cm"})
                browser.close()
            return pdf_bytes
        except Exception:
            logging.error("PDF generation failed", exc_info=True)
            raise

    @staticmethod
    def _render_chart_png(daily_totals: dict, windows: list) -> str:
        # unpack date range
        oldest_iso, _ = windows[0]
        _, newest_iso = windows[-1]
        oldest = isoparse(oldest_iso).date()
        newest = isoparse(newest_iso).date()

        # build full date list
        days = []
        d = oldest
        while d <= newest:
            days.append(d)
            d += timedelta(days=1)

        hours = [daily_totals.get(day.isoformat(), 0) for day in days]

        # larger figure
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(days, hours, width=0.8)
        ax.set_xlim(oldest, newest)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.xaxis.set_minor_locator(mdates.DayLocator(interval=7))
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        ax.set_title("Time Delivered by Day")
        ax.set_ylabel("Hours")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    @staticmethod
    def _fetch_all_entries(query):
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
        base = dt_module.datetime.strptime(
            f"01-{month_year}", "%d-%m-%Y") - relativedelta(months=1)
        adj = base - relativedelta(months=offset)
        start = adj.replace(day=26)
        end = (start + relativedelta(months=1)).replace(day=25)
        return start.date().isoformat(), end.date().isoformat()
