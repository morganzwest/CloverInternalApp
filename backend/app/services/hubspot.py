import os
import requests
from typing import List, Dict, Optional
from supabase import Client
from app.supabase.client import supabase
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import math


HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")
BASE_URL = "https://api.hubapi.com"
session = requests.Session()
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_API_KEY}",
    "Content-Type": "application/json"
}


def as_float(v, default=0.0):
    if v is None:
        return default
    try:
        return float(str(v).strip().replace(",", "."))
    except ValueError:
        return default


def as_int(v, default=0, mode="round"):
    x = as_float(v, default)
    if mode == "floor":
        return math.floor(x)
    if mode == "ceil":
        return math.ceil(x)
    return int(round(x))


def fetch_all_companies(limit: int = 100) -> List[Dict]:
    print("[fetch_all_companies] Starting fetch_all_companies with limit =", limit)
    property_names = get_company_property_names()
    print("[fetch_all_companies] Using properties:", property_names)
    url = f"{BASE_URL}/crm/v3/objects/companies"
    params = {"limit": limit, "properties": ",".join(property_names)}
    results = []
    page = 1

    while url:
        print(
            f"[fetch_all_companies] Fetching page {page}: {url} with params {params}")
        res = session.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        data = res.json()
        batch = data.get("results", [])
        results.extend(batch)
        print(
            f"[fetch_all_companies]   → Retrieved {len(batch)} records (total so far: {len(results)})")

        url = data.get("paging", {}).get("next", {}).get("link")
        params = {}  # clear params for subsequent pages
        page += 1

    print(
        f"[fetch_all_companies] Completed fetch: {len(results)} total records")
    return results


def get_time_entry_property_names() -> List[str]:
    print("[get_time_entry_property_names] Fetching time entry schema properties")
    schema_id = "2-142987565"  # objectTypeId found in your payload
    url = f"{BASE_URL}/crm/v3/schemas/{schema_id}"
    print(f"[get_time_entry_property_names] GET {url}")
    res = session.get(url, headers=HEADERS)
    res.raise_for_status()
    data = res.json()
    props = data.get("properties", [])
    print(
        f"[get_time_entry_property_names] Fetched {len(props)} properties from schema.")
    return [prop["name"] for prop in props]


def get_company_property_names() -> List[str]:
    print("[get_company_property_names] Returning hard-coded company property list")
    #     url = f"{BASE_URL}/crm/v3/properties/companies"
    #     res = requests.get(url, headers=HEADERS)
    #     res.raise_for_status()
    #     data = res.json()
    #     print(
    #         f"Fetched {len(data.get('results', []))} company properties from HubSpot.")
    #     return [prop["name"] for prop in data.get("results", [])]
    props = [
        "name",
        "domain",
        "client_code",
        "industry",
        "region",
        "type",
        "status",
        "contract_start_date",
        "contract_end_date",
        "contract_term__months_",
        "annual_charge",
        "hours_per_month",
        "income_per_month",
        "off_boarded",
        "original_clover_start_date",
        "off_boarding_date",
        "contract_status",
        "lifecyclestage",
        "hubspot_owner_id"
    ]
    print(f"[get_company_property_names] Property names: {props}")
    return props


def upsert_companies_to_supabase(companies: List[Dict]) -> None:
    print(
        f"[upsert_companies_to_supabase] Upserting {len(companies)} companies to Supabase")
    batch = []

    for idx, company in enumerate(companies, start=1):
        print(
            f"[upsert_companies_to_supabase] Processing company {idx}/{len(companies)}: ID {company.get('id')}")
        props = company.get("properties", {})

        record = {
            "hubspot_id": int(company["id"]),
            "name": props.get("name"),
            "domain": props.get("domain"),
            "client_code": props.get("client_code"),
            "industry": props.get("industry"),
            "region": props.get("region"),
            "type": props.get("type"),
            "status": props.get("status"),
            "contract_term__months_": int(props.get("contract_term__months_")) if props.get("contract_term__months_") else None,
            "annual_charge": float(props.get("annual_charge") or 0),
            "hours_per_month": float(props.get("hours_per_month") or 0),
            "income_per_month": float(props.get("income_per_month") or 0),
            "off_boarded": props.get("off_boarded") == "true",
            "contract_status": props.get("contract_status"),
            "lifecycle_stage": props.get("lifecyclestage"),
            "owner_id": props.get("hubspot_owner_id"),
            "created_at": company.get("createdAt"),
            "updated_at": company.get("updatedAt"),
            "contract_start_date": props.get("contract_start_date") or None,
            "contract_end_date": props.get("contract_end_date") or None,
            "original_clover_start_date": props.get("original_clover_start_date") or None,
            "off_boarding_date": props.get("off_boarding_date") or None,
            "raw": props
        }

        batch.append(record)

    print(
        f"[upsert_companies_to_supabase] Total records prepared: {len(batch)}")
    # Chunk to avoid payload limits
    chunk_size = 100
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i:i + chunk_size]
        print(
            f"[upsert_companies_to_supabase] Upserting chunk {i // chunk_size + 1} ({len(chunk)} records)")
        supabase.table("hubspot_companies").upsert(
            chunk, on_conflict="hubspot_id"
        ).execute()

    print("[upsert_companies_to_supabase] Upsert complete.")


def map_owner_ids_to_users(
    owner_ids: List[int], users: List[Dict]
) -> Dict[int, Optional[Dict]]:
    """
    Given a list of owner_ids and a list of user objects (from fetch_all_users),
    return a mapping of owner_id → user object (or None if not found).
    """
    # Build a fast lookup by HubSpot owner ID
    user_by_id = {int(u["id"]): u for u in users}
    mapping: Dict[int, Optional[Dict]] = {}
    for oid in owner_ids:
        mapping[oid] = user_by_id.get(oid)
        if mapping[oid] is None:
            print(f"[map_owner_ids_to_users] No user found for owner_id={oid}")
    return mapping

# 1) Raw HubSpot fetch—no inserts here


def _raw_fetch_all_users(limit: int = 100) -> List[Dict]:
    print(f"[_raw_fetch_all_users] Starting fetch with page size {limit}")
    url = f"{BASE_URL}/crm/v3/owners"
    params = {"limit": limit}
    results: List[Dict] = []

    try:
        while url:
            print(f"[ _raw_fetch_all_users] GET {url} params={params}")
            res = session.get(url, headers=HEADERS, params=params)
            if res.status_code == 403:
                print(
                    "[_raw_fetch_all_users] ⚠️ 403 Forbidden – skipping owner fetch")
                return []
            res.raise_for_status()
            data = res.json()

            batch = data.get("results", [])
            print(f"[_raw_fetch_all_users] Retrieved {len(batch)} users")
            results.extend(batch)

            url = data.get("paging", {}).get("next", {}).get("link")
            params = {}
    except Exception as e:
        print(f"[_raw_fetch_all_users] ⚠️ Error fetching users: {e}")
        return []

    print(
        f"[_raw_fetch_all_users] Completed fetch: {len(results)} total users")
    return results


def insert_new_owners_to_supabase(
    users: List[Dict], chunk_size: int = 100
) -> int:
    """
    Given a list of HubSpot owner dicts, insert only those
    whose hubspot_id isn’t already in the `owners` table.
    Returns number of new records inserted.
    """
    if not users:
        print("[insert_new_owners_to_supabase] No users provided, aborting.")
        return 0

    # 1) Build default owner records
    records = [
        {"hubspot_id": int(u["id"]), "contracted_hours": 0,
         "hourly_rate": None}
        for u in users
    ]

    # 2) Fetch existing IDs from Supabase
    existing = supabase.table("owners").select(
        "hubspot_id").execute().data or []
    existing_ids = {r["hubspot_id"] for r in existing}
    print(
        f"[insert_new_owners_to_supabase] Found {len(existing_ids)} existing owners")

    # 3) Filter out ones we already have
    new_records = [r for r in records if r["hubspot_id"] not in existing_ids]
    if not new_records:
        print("[insert_new_owners_to_supabase] No new owners to insert")
        return 0

    print(
        f"[insert_new_owners_to_supabase] Inserting {len(new_records)} new owners...")

    # 4) Insert in chunks
    inserted = 0
    for i in range(0, len(new_records), chunk_size):
        chunk = new_records[i: i + chunk_size]
        try:
            supabase.table("owners").insert(chunk).execute()
            inserted += len(chunk)
            print(
                f"[insert_new_owners_to_supabase] → Inserted chunk {i//chunk_size+1} ({len(chunk)} records)")
        except Exception as e:
            print(
                f"[insert_new_owners_to_supabase] ❌ Failed to insert chunk {i//chunk_size+1}: {e}")

    print(
        f"[insert_new_owners_to_supabase] Done. Total new owners inserted: {inserted}")
    return inserted


def fetch_all_users(limit: int = 100) -> List[Dict]:
    """
    Fetch all HubSpot owners *and* upsert any new ones into Supabase,
    then return the list of owners.
    """
    users = _raw_fetch_all_users(limit)
    if users:
        insert_new_owners_to_supabase(users)
    return users


def fetch_all_time_entries(limit: int = 100) -> List[Dict]:
    print("[fetch_all_time_entries] Starting fetch_all_time_entries with limit =", limit)
    property_names = get_time_entry_property_names()
    print("[fetch_all_time_entries] Using properties:", property_names)
    object_type = "p25086185_time_entries"  # your fullyQualifiedName from payload
    url = f"{BASE_URL}/crm/v3/objects/{object_type}"
    params = {
        "limit": limit,
        "properties": ",".join(property_names),
        "associations": "company"
    }
    results = []
    page = 1

    while url:
        print(
            f"[fetch_all_time_entries] Fetching page {page}: {url} with params {params}")
        res = session.get(url, headers=HEADERS, params=params)
        res.raise_for_status()
        data = res.json()
        batch = data.get("results", [])
        print(f"[fetch_all_time_entries]   → Retrieved {len(batch)} records")
        results.extend(batch)
        url = data.get("paging", {}).get("next", {}).get("link", None)
        params = {}
        page += 1

    print(
        f"[fetch_all_time_entries] Completed fetch: {len(results)} total records")
    return results


def upsert_time_entries_to_supabase(entries: List[Dict]) -> None:
    print(
        f"[upsert_time_entries_to_supabase] Upserting {len(entries)} time entries to Supabase")
    batch = []

    for idx, entry in enumerate(entries, start=1):
        props = entry.get("properties", {})
        print(
            f"[upsert_time_entries_to_supabase] Processing entry {idx}/{len(entries)}: ID {entry.get('id')}")

        if "associations" in entry:
            print(
                f"[upsert_time_entries_to_supabase] Associations for entry {entry['id']}: {entry['associations']}")

        record = {
            "hubspot_id": int(entry["id"]),
            "company_hubspot_id": int(entry["associations"]["companies"]["results"][0]["id"])
            if entry.get("associations", {}).get("companies", {}).get("results") else None,
            "start_time": props.get("start_time"),
            "end_time": props.get("end_time"),
            "hours": as_float(props.get("time_spent___hours")),
            "minutes": as_int(props.get("time_spent___minutes"), mode="round"),
            "entry_type": props.get("entry_type"),
            "description": props.get("description"),
            "tag": props.get("tag"),
            "owner_id": props.get("hubspot_owner_id"),
            "created_at": props.get("hs_createdate"),
            "updated_at": props.get("hs_lastmodifieddate"),
            "source": "HubSpot",
            "raw": props
        }
        batch.append(record)

    print(
        f"[upsert_time_entries_to_supabase] Total records prepared: {len(batch)}")

    def _upsert_chunk(chunk: List[Dict]):
        attempts = 0
        while attempts < 3:
            try:
                supabase.table("time_entries").upsert(
                    chunk, on_conflict="hubspot_id").execute()
                print(
                    f"[upsert_time_entries_to_supabase]   → Successfully upserted {len(chunk)} records")
                return
            except Exception as e:
                attempts += 1
                print(
                    f"[upsert_time_entries_to_supabase]   ⚠️ Attempt {attempts} failed: {e}")
                time.sleep(attempts * 2)
        print(
            f"[upsert_time_entries_to_supabase]   ❌ Giving up on chunk of {len(chunk)} records after 3 attempts")

    chunk_size = 50
    for i in range(0, len(batch), chunk_size):
        chunk = batch[i: i + chunk_size]
        print(
            f"[upsert_time_entries_to_supabase] Upserting chunk {i // chunk_size + 1} ({len(chunk)} records)")
        _upsert_chunk(chunk)

    print("[upsert_time_entries_to_supabase] Upsert complete.")


def sync_all_data():
    print("[sync_all_data] Starting full sync")
    print("[sync_all_data] Fetching HubSpot companies...")
    companies = fetch_all_companies()
    upsert_companies_to_supabase(companies)

    print("[sync_all_data] Fetching Time Entries...")
    time_entries = fetch_all_time_entries()
    print(
        f"[sync_all_data] Fetched {len(time_entries)} time entries. Upserting...")
    upsert_time_entries_to_supabase(time_entries)

    print("✅ HubSpot sync complete.")


def time_sync():
    print("[time_sync] Starting time sync")
    print("[time_sync] Fetching Time Entries...")
    time_entries = fetch_all_time_entries()
    print(
        f"[time_sync] Fetched {len(time_entries)} time entries. Upserting...")
    upsert_time_entries_to_supabase(time_entries)

    print("✅ HubSpot time sync complete.")
