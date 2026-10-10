"""Cloud internship watcher (stdlib only, runs on GitHub Actions every 10 min, Mac can be off).

Sources: SimplifyJobs + vanshb03 community lists (thousands of companies, with a sponsorship field), Greenhouse /
Lever / Ashby / SmartRecruiters boards and Workday tenants listed in boards.txt. New technical US internships that
don't rule out sponsorship are pushed to ntfy (topic from the NTFY_TOPIC secret). State: seen.json.
First run seeds seen.json silently so you aren't flooded.   Self-check: python watch_cloud.py --test
"""
import html
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
SEEN = ROOT / "seen.json"
LISTS = ["https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json",
         "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json"]

TITLE_OK = re.compile(r"\bintern(ship)?\b|co-?op", re.I)
TECH = re.compile(r"software|\bswe\b|engineer|developer|programmer|\bdata\b|machine learning|\bml\b|\bai\b|artificial intelligence|"
                  r"back.?end|full.?stack|front.?end|infrastructure|platform|cloud|devops|\bsre\b|reliability|systems|"
                  r"security|computational|quantitative develop|quant dev", re.I)
TITLE_BAD = re.compile(r"\bph\.?d\b|high school|winter|fall 20\d\d|spring 20\d\d|\bmba\b|master.?s|graduate intern|micro-intern|"
                       r"mechanical|civil|chemical|electrical|hardware|asic|fpga|analog|\bic design|manufacturing|"
                       r"architectural|hvac|firmware|marketing|accounting|audit|finance|legal|recruit", re.I)
US_STRONG = re.compile(r"united states|\busa\b|\bus\b|remote|new york|nyc|san francisco|bay area|seattle|chicago|austin|boston|"
                       r"los angeles|mountain view|palo alto|menlo park|san jose|sunnyvale|denver|atlanta|miami|santa clara|"
                       r"redmond|pittsburgh|washington", re.I)
US_STATE = re.compile(r"\b(AL|AZ|CA|CO|CT|DC|FL|GA|IL|IN|MA|MD|MI|MN|NC|NJ|NY|OH|OR|PA|TX|UT|VA|WA|WI)\b")
NON_US = re.compile(r"canada|toronto|vancouver|montreal|london|united kingdom|\buk\b|ireland|dublin|germany|berlin|munich|"
                    r"france|paris|netherlands|amsterdam|switzerland|zurich|zug|spain|madrid|poland|serbia|romania|bucharest|"
                    r"india|bangalore|bengaluru|hyderabad|gurgaon|singapore|hong kong|china|shanghai|japan|tokyo|korea|"
                    r"seoul|australia|sydney|israel|tel aviv|mexico|brazil|qatar|doha", re.I)
BLOCKERS = re.compile(r"(unable|not able|will not|won.t|cannot|can.t|do(es)? not)\s+(to\s+)?(provide\s+|offer\s+)?"
                      r"(visa\s+|immigration\s+)?sponsor|without (the need for )?(current or future |now or in the future )?"
                      r"(visa |employment |immigration )?sponsorship|u\.?s\.? citizen(ship)?\s+(is\s+)?required|"
                      r"must be a u\.?s\.? citizen|security clearance|\bu\.?s\.? persons?\b|itar", re.I)


def get(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"User-Agent": "internship-watch/1.0", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def strip(s):
    return re.sub(r"<[^>]+>", " ", html.unescape(s or ""))


def verdict(title, location, description=""):
    """'' if worth alerting, else the reason it's dropped."""
    if not TITLE_OK.search(title) or not TECH.search(title) or TITLE_BAD.search(title):
        return "title"
    if location.strip() and not (US_STRONG.search(location) or (US_STATE.search(location) and not NON_US.search(location))):
        return "location"
    if BLOCKERS.search(description):
        return "sponsorship"
    return ""


# ---------- sources: each yields (url, company, title, location, description) ----------

def community_lists():
    for src in LISTS:
        for j in get(src):
            if not (j.get("active") and j.get("is_visible", True)):
                continue
            if j.get("sponsorship") in ("Does Not Offer Sponsorship", "U.S. Citizenship is Required"):
                continue
            terms = " ".join(j.get("terms") or [j.get("season") or ""])
            if terms and "summer" not in terms.lower():
                continue
            yield j["url"], j.get("company_name", ""), j.get("title", ""), "; ".join(j.get("locations") or []), ""


def board(ats, token):
    if ats == "greenhouse":
        for j in get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true").get("jobs", []):
            yield (f"https://job-boards.greenhouse.io/{token}/jobs/{j['id']}", token, j["title"],
                   (j.get("location") or {}).get("name", ""), strip(j.get("content")))
    elif ats == "lever":
        for j in get(f"https://api.lever.co/v0/postings/{token}?mode=json"):
            yield (j["hostedUrl"], token, j["text"], (j.get("categories") or {}).get("location", "") or "",
                   f"{j.get('descriptionPlain', '')} " + " ".join(strip(l.get("content")) for l in j.get("lists", [])))
    elif ats == "ashby":
        for j in get(f"https://api.ashbyhq.com/posting-api/job-board/{token}").get("jobs", []):
            if j.get("isListed", True):
                yield j["jobUrl"], token, j["title"], j.get("location", "") or "", j.get("descriptionPlain", "")
    elif ats == "smartrecruiters":
        for j in get(f"https://api.smartrecruiters.com/v1/companies/{token}/postings?q=intern&limit=100").get("content", []):
            loc = j.get("location") or {}
            yield (f"https://jobs.smartrecruiters.com/{token}/{j['id']}", token, j["name"],
                   ", ".join(filter(None, [loc.get("city"), loc.get("region"), loc.get("country")])), "")
    elif ats == "workday":  # token = "tenant/wdN/site"
        tenant, wd, site = token.split("/")
        base = f"https://{tenant}.{wd}.myworkdayjobs.com"
        d = get(f"{base}/wday/cxs/{tenant}/{site}/jobs", {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "intern"})
        for j in d.get("jobPostings", []):
            yield f"{base}/en-US/{site}{j['externalPath']}", tenant, j["title"], j.get("locationsText", ""), ""


def boards():
    lines = (ROOT / "boards.txt").read_text().splitlines() if (ROOT / "boards.txt").exists() else []
    return [tuple(l.split(":", 1)) for l in (l.strip() for l in lines) if l and not l.startswith("#") and ":" in l]


def push(title, body, click=""):
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        print(f"(no NTFY_TOPIC) {title}: {body}")
        return
    headers = {"Title": title.encode("ascii", "ignore").decode(), "Tags": "briefcase"}
    if click:
        headers["Click"] = click
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), headers=headers, method="POST")
    urllib.request.urlopen(req, timeout=20)


def main():
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    first_run = not seen
    new, errors = [], []
    sources = [("lists", community_lists)] + [(f"{a}:{t}", (lambda a=a, t=t: board(a, t))) for a, t in boards()]
    for name, fetch in sources:
        try:
            for url, company, title, location, desc in fetch():
                if url in seen:
                    continue
                seen.add(url)
                if not verdict(title, location, desc):
                    new.append((company, title, location, url))
        except Exception as e:
            errors.append(f"{name}: {str(e)[:80]}")
    SEEN.write_text(json.dumps(sorted(seen), indent=0))
    print(f"{time.strftime('%Y-%m-%d %H:%M')} sources={len(sources)} new={len(new)} seen={len(seen)} errors={len(errors)}")
    for e in errors:
        print("  error", e)
    if first_run:
        print("first run: seeded seen.json without notifying")
        return
    if 0 < len(new) <= 5:
        for company, title, location, url in new:
            push(f"New internship: {company}", f"{title}\n{location}", click=url)
    elif new:
        lines = [f"{c}: {t}" for c, t, _, _ in new[:15]]
        push(f"{len(new)} new internships", "\n".join(lines) + (f"\n+{len(new) - 15} more" if len(new) > 15 else ""))


if __name__ == "__main__":
    if "--test" in sys.argv:
        assert verdict("Software Engineer Intern (Summer 2027)", "New York, NY") == ""
        assert verdict("Accounting Intern", "New York, NY") == "title"
        assert verdict("SWE Intern", "Toronto, ON, CA") == "location"
        assert verdict("SWE Intern", "London, UK") == "location"
        assert verdict("SWE Intern", "Remote in USA") == ""
        assert verdict("SWE Intern", "Austin, TX", "We are unable to sponsor visas.") == "sponsorship"
        assert verdict("Machine Learning Intern - Winter 2027", "SF") == "title"
        print("watch_cloud.py self-check ok")
    else:
        main()
