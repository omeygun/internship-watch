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

4. External trigger (GitHub drops most `*/10` scheduled runs, so the cron in the workflow is only a backup):
   - Fine-grained token: Settings → Developer settings → Fine-grained tokens, repo `internship-watch` only,
     permission **Actions: Read and write**.
   - [cron-job.org](https://cron-job.org) job, every 10 min: `POST
     https://api.github.com/repos/omeygun/internship-watch/actions/workflows/watch.yml/dispatches`, headers
     `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`, body `{"ref":"main"}`. Expect HTTP 204.

`seen.json` remembers what has already been reported. A newly added board is seeded silently on its first run.
Delete `seen.json` to re-seed everything silently.
Self-check: `python3 watch_cloud.py --test`.
