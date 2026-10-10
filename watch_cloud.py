"""Cloud internship watcher (stdlib only, runs on GitHub Actions every 10 min, Mac can be off).

Sources: SimplifyJobs + vanshb03 community lists (thousands of companies, with a sponsorship field), Greenhouse /
Lever / Ashby / SmartRecruiters boards and Workday tenants listed in boards.txt. New technical US internships that
don't rule out sponsorship are pushed to ntfy (topic from the NTFY_TOPIC secret). State: seen.json.
Each source's first fetch seeds seen.json silently so you aren't flooded.   Self-check: python watch_cloud.py --test
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
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
TITLE_BAD = re.compile(r"\bph\.?d\b|high school|winter|fall 20\d\d|spring 20\d\d|\bmba\b|graduate intern|micro-intern|"
                       r"mechanical|civil|chemical|electrical|hardware|asic|fpga|analog|\bic design|manufacturing|"
                       r"architectural|hvac|firmware|marketing|accounting|audit|finance|legal|recruit", re.I)
US_STRONG = re.compile(r"united states|\busa\b|\bus\b|new york|nyc|san francisco|bay area|seattle|chicago|austin|boston|"
                       r"los angeles|mountain view|palo alto|menlo park|san jose|sunnyvale|denver|atlanta|miami|santa clara|"
                       r"redmond|pittsburgh|washington", re.I)
US_STATE = re.compile(r"\b(AL|AK|AZ|AR|CA|CO|CT|DC|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|"
                      r"NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|SF|NYC)\b")  # case-sensitive; LA = Louisiana or Los Angeles
US_STATE_NAME = re.compile(r"alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|"
                           r"idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|"
                           r"minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|"
                           r"north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|"
                           r"south dakota|tennessee|texas|utah|vermont|virginia|wisconsin|wyoming", re.I)
CA_PROVINCE = re.compile(r"\b(ON|BC|QC|AB)\b")  # case-sensitive, so "On-site" isn't Ontario
NON_US = re.compile(r"canada|toronto|vancouver|montreal|waterloo|ottawa|calgary|edmonton|ontario|british columbia|"
                    r"london|united kingdom|\buk\b|ireland|dublin|germany|berlin|munich|"
                    r"france|paris|netherlands|amsterdam|switzerland|zurich|zug|spain|madrid|poland|serbia|romania|bucharest|"
                    r"india|bangalore|bengaluru|hyderabad|gurgaon|singapore|hong kong|china|shanghai|japan|tokyo|korea|"
                    r"seoul|australia|sydney|israel|tel aviv|mexico|brazil|qatar|doha|costa rica|argentina|colombia|chile|taiwan|"
                    r"vietnam|philippines|malaysia|penang|czech|prague|portugal|lisbon|italy|milan|sweden|denmark|finland", re.I)
BLOCKERS = re.compile(r"(unable|not able|will not|won.t|cannot|can.t|do(es)? not)\s+(to\s+)?(provide\s+|offer\s+)?"
                      r"(visa\s+|immigration\s+)?sponsor|without (the need for )?(current or future |now or in the future )?"
                      r"(visa |employment |immigration )?sponsorship|u\.?s\.? citizen(ship)?\s+(is\s+)?required|"
                      r"must be a u\.?s\.? citizen|(?<!no )security clearance|\bu\.?s\.? persons?\b|\bitar\b", re.I)


def get(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 headers={"User-Agent": "internship-watch/1.0", "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def strip(s):
    return re.sub(r"<[^>]+>", " ", html.unescape(s or ""))


def is_us(place):
    """One location ("Austin, TX", "Remote - India"). Workday's "2 Locations" is handled by the caller."""
    if NON_US.search(place) or CA_PROVINCE.search(place):
        return False
    return bool(US_STRONG.search(place) or US_STATE.search(place) or US_STATE_NAME.search(place) or re.search(r"remote|virtual", place, re.I))


def verdict(title, location, description=""):
    """'' if worth alerting, else the reason it's dropped."""
    if not TITLE_OK.search(title) or not TECH.search(title) or TITLE_BAD.search(title):
        return "title"
    if location.strip() and not re.fullmatch(r"\s*\d+ locations\s*", location, re.I) and not any(map(is_us, location.split(";"))):
        return "location"
    if BLOCKERS.search(description):
        return "sponsorship"
    return ""


def key(company, title, location):
    """Same role reposted under a new requisition (RTX does this) gets a new URL but the same key."""
    t = re.sub(r"[^a-z0-9]+", " ", title.lower()).replace("engineering", "engineer").strip()
    return f"job:{company.lower()}|{t}|{location.lower()}"


# ---------- sources: each yields (url, company, title, location, description) ----------

def community_list(src):
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
        offset, total = 0, 1
        while offset < min(total, 200):  # Workday caps pages at 20 and only reports total on the first page
            d = get(f"{base}/wday/cxs/{tenant}/{site}/jobs",
                    {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": "intern"})
            jobs = d.get("jobPostings", [])
            if offset == 0:
                total = d.get("total", 0)
            if not jobs:
                break
            for j in jobs:
                yield f"{base}/en-US/{site}{j['externalPath']}", tenant, j["title"], j.get("locationsText", ""), ""
            offset += 20


def boards():
    lines = (ROOT / "boards.txt").read_text().splitlines() if (ROOT / "boards.txt").exists() else []
    return [tuple(l.split(":", 1)) for l in (l.strip() for l in lines) if l and not l.startswith("#") and ":" in l]


def push(title, body, click=""):
    """True if sent (or no topic configured). Never raises, so one bad alert can't wedge the run."""
    topic = os.environ.get("NTFY_TOPIC", "")
    if not topic:
        print(f"(no NTFY_TOPIC) {title}: {body}")
        return True
    headers = {"Title": title.encode("ascii", "ignore").decode(), "Tags": "briefcase"}
    if click:
        headers["Click"] = urllib.parse.quote(click, safe=":/?#[]@!$&'()*+,;=%~")  # headers must be latin-1
    try:
        req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception as e:
        print(f"  push failed ({title}): {str(e)[:80]}")
        return False


def main():
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    new, errors, seeded_now = [], [], []
    sources = ([(f"list:{u}", (lambda u=u: community_list(u))) for u in LISTS] +
               [(f"{a}:{t}", (lambda a=a, t=t: board(a, t))) for a, t in boards()])
    for name, fetch in sources:
        # A source's first successful fetch seeds silently, so a new boards.txt line doesn't flood you.
        seeded = f"src:{name}" in seen
        try:
            for url, company, title, location, desc in fetch():
                k = key(company, title, location)
                if url in seen or k in seen:
                    continue
                seen.update((url, k))
                if seeded and not verdict(title, location, desc):
                    new.append((company, title, location, url, k))
        except Exception as e:
            errors.append(f"{name}: {str(e)[:80]}")
            continue
        if not seeded:
            seen.add(f"src:{name}")
            seeded_now.append(name)
    print(f"{time.strftime('%Y-%m-%d %H:%M')} sources={len(sources)} new={len(new)} seen={len(seen)} errors={len(errors)}")
    for e in errors:
        print("  error", e)
    for name in seeded_now:
        print("  seeded silently:", name)
    if 0 < len(new) <= 5:
        for company, title, location, url, k in new:
            if not push(f"New internship: {company}", f"{title}\n{location}", click=url):
                seen.difference_update((url, k))  # retry next run
    elif new:
        lines = [f"{c}: {t}" for c, t, *_ in new[:15]]
        if not push(f"{len(new)} new internships", "\n".join(lines) + (f"\n+{len(new) - 15} more" if len(new) > 15 else "")):
            for *_, url, k in new:
                seen.difference_update((url, k))
    SEEN.write_text(json.dumps(sorted(seen), indent=0))


if __name__ == "__main__":
    if "--test" in sys.argv:
        assert verdict("Software Engineer Intern (Summer 2027)", "New York, NY") == ""
        assert verdict("Accounting Intern", "New York, NY") == "title"
        assert verdict("SWE Intern", "Toronto, ON, CA") == "location"
        assert verdict("SWE Intern", "London, UK") == "location"
        assert verdict("SWE Intern", "Remote in USA") == ""
        assert verdict("SWE Intern", "Austin, TX", "We are unable to sponsor visas.") == "sponsorship"
        assert verdict("Machine Learning Intern - Winter 2027", "SF") == "title"
        assert verdict("SWE Intern", "New York, NY", "race, military or veteran status") == ""
        assert verdict("SWE Intern", "Austin, TX", "Subject to ITAR.") == "sponsorship"
        assert verdict("SWE Intern", "Austin, TX", "No security clearance required.") == ""
        assert verdict("SWE Intern", "Remote - India") == "location"
        assert verdict("SWE Intern", "Waterloo, ON, CA") == "location"
        assert verdict("SWE Intern", "On-site - Austin, TX") == ""
        assert verdict("SWE Intern", "New York, NY; London, UK") == ""
        assert verdict("SWE Intern", "Costa Rica, San Jose") == "location"
        assert verdict("SWE Intern", "2 Locations") == ""
        assert verdict("SWE Intern", "Virtual US") == ""
        for place in ("Lincoln, NE", "St. Louis, MO", "California", "SF", "LA", "Tulsa, OK"):
            assert verdict("SWE Intern", place) == "", place
        assert verdict("Software Engineer Intern (Bachelor's/Master's)", "Seattle, WA") == ""
        assert key("RTX", "Software Engineering Intern", "Melbourne, FL") == key("RTX", "Software Engineer Intern", "Melbourne, FL")
        print("watch_cloud.py self-check ok")
    else:
        main()
