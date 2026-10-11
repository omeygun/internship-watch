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
4. Start it once: Actions → watch → Run workflow.

**Scheduling:** GitHub drops most scheduled runs (we saw 4–7 hour gaps), so each run sleeps 9 min and then dispatches
the next one with the built-in token. The cron is only there to restart the chain if it ever breaks. To stop it,
disable the workflow (Actions → watch → ⋯ → Disable workflow).

`seen.json` remembers what has already been reported. A newly added board is seeded silently on its first run.
Delete `seen.json` to re-seed everything silently.
Self-check: `python3 watch_cloud.py --test`.
