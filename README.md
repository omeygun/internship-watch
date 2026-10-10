# internship-watch

Checks for new software / ML / data internships every 10 minutes on GitHub Actions and pushes each one to a phone via
[ntfy](https://ntfy.sh). Runs in the cloud, so nothing needs to be on.

**Sources:** the [SimplifyJobs](https://github.com/SimplifyJobs/Summer2027-Internships) and
[vanshb03](https://github.com/vanshb03/Summer2027-Internships) community lists, plus every board in `boards.txt`
(Greenhouse, Lever, Ashby, SmartRecruiters, Workday).

**Filters:** internship/co-op titles in software, ML, data or infrastructure; US or remote; skips postings that say
they won't sponsor visas or need US citizenship / clearance.

## Setup

1. Install the ntfy app and subscribe to your topic.
2. Repo secret `NTFY_TOPIC` = your topic name (Settings → Secrets → Actions).
3. Add companies to `boards.txt` (`greenhouse:stripe`, `lever:palantir`, `ashby:notion`, `smartrecruiters:Visa`,
   `workday:nvidia/wd5/NVIDIAExternalCareerSite`).

`seen.json` remembers what has already been reported. Delete it to re-seed silently on the next run.
Self-check: `python3 watch_cloud.py --test`.
