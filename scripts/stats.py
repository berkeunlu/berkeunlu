import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape

API = "https://api.github.com/graphql"
TOKEN = os.environ["STATS_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/stats.svg"
TOP_LANGS = 6
IGNORE_LANGS = {"CMake", "Dockerfile", "Makefile", "Shell", "Batchfile"}

LANG_FIELDS = "languages(first: 15, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } }"


def gql(query, **variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def year_window(year, now):
    start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
    end = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
    return start.isoformat(), end.isoformat()


YEAR_Q = (
    """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
      commitContributionsByRepository(maxRepositories: 100) {
        repository { nameWithOwner isFork %s }
        contributions { totalCount }
      }
    }
  }
}
"""
    % LANG_FIELDS
)

OWNED_Q = (
    """
query($after: String) {
  viewer {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false) {
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner %s }
    }
  }
}
"""
    % LANG_FIELDS
)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    created = gql("{ viewer { createdAt login } }")["viewer"]
    first_year = int(created["createdAt"][:4])

    totals = dict(commits=0, prs=0, reviews=0, issues=0)
    repos = {}
    commits = {}
    for year in range(first_year, now.year + 1):
        f, t = year_window(year, now)
        c = gql(YEAR_Q, **{"from": f, "to": t})["viewer"]["contributionsCollection"]
        totals["commits"] += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        totals["prs"] += c["totalPullRequestContributions"]
        totals["reviews"] += c["totalPullRequestReviewContributions"]
        totals["issues"] += c["totalIssueContributions"]
        for item in c["commitContributionsByRepository"]:
            r = item["repository"]
            repos[r["nameWithOwner"]] = r
            commits[r["nameWithOwner"]] = commits.get(r["nameWithOwner"], 0) + item["contributions"]["totalCount"]

    after = None
    while True:
        page = gql(OWNED_Q, after=after)["viewer"]["repositories"]
        for r in page["nodes"]:
            repos.setdefault(r["nameWithOwner"], r)
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]

    langs = {}
    for name, r in repos.items():
        if r.get("isFork"):
            continue
        edges = [e for e in r["languages"]["edges"] if e["node"]["name"] not in IGNORE_LANGS]
        repo_bytes = sum(e["size"] for e in edges) or 1
        weight = commits.get(name, 1)
        for e in edges:
            n = e["node"]["name"]
            share, color = langs.get(n, (0.0, e["node"]["color"] or "#888"))
            langs[n] = (share + weight * e["size"] / repo_bytes, color)

    ranked = sorted(langs.items(), key=lambda kv: -kv[1][0])[:TOP_LANGS]
    total_bytes = sum(s for _, (s, _) in ranked) or 1
    lang_rows = [(n, c, s / total_bytes * 100) for n, (s, c) in ranked]

    stats = [
        ("Commits", totals["commits"]),
        ("Pull requests", totals["prs"]),
        ("Code reviews", totals["reviews"]),
        ("Issues", totals["issues"]),
        ("Repositories", len(repos)),
    ]
    since = f"{first_year} – {now.year}"
    with open(OUT, "w") as fh:
        fh.write(render(stats, lang_rows, since))
    print(totals, len(repos), [(n, round(p, 1)) for n, _, p in lang_rows])


def render(stats, lang_rows, since):
    w, h = 640, 230
    rows = []
    for i, (label, value) in enumerate(stats):
        y = 82 + i * 30
        rows.append(f'<text x="30" y="{y}" class="label">{escape(label)}</text>')
        rows.append(f'<text x="200" y="{y}" class="value" text-anchor="end">{value:,}</text>')

    bar_x, bar_w = 270, 340
    bar, x = [], bar_x
    for _, color, pct in lang_rows:
        seg = bar_w * pct / 100
        bar.append(f'<rect x="{x:.1f}" y="62" width="{seg:.1f}" height="10" fill="{color}"/>')
        x += seg

    legend = []
    for i, (name, color, pct) in enumerate(lang_rows):
        col, row = i % 2, i // 2
        lx, ly = bar_x + col * 175, 105 + row * 28
        legend.append(f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>')
        legend.append(f'<text x="{lx + 18}" y="{ly}" class="lang">{escape(name)} <tspan class="pct">{pct:.1f}%</tspan></text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub all-time stats">
<style>
:root {{ --bg:#ffffff; --border:#d0d7de; --title:#0969da; --text:#1f2328; --muted:#656d76; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#0d1117; --border:#30363d; --title:#58a6ff; --text:#e6edf3; --muted:#8b949e; }} }}
text {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; }}
.title {{ font-size:18px; font-weight:600; fill:var(--title); }}
.sub {{ font-size:12px; fill:var(--muted); }}
.label {{ font-size:14px; fill:var(--text); }}
.value {{ font-size:14px; font-weight:600; fill:var(--text); }}
.lang {{ font-size:13px; fill:var(--text); }}
.pct {{ fill:var(--muted); }}
.head {{ font-size:12px; font-weight:600; fill:var(--muted); letter-spacing:.5px; }}
</style>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="8" fill="var(--bg)" stroke="var(--border)"/>
<text x="30" y="36" class="title">GitHub, all time</text>
<text x="{w - 30}" y="36" class="sub" text-anchor="end">{since} · private repositories included</text>
<text x="{bar_x}" y="55" class="head">TOP LANGUAGES</text>
<clipPath id="r"><rect x="{bar_x}" y="62" width="{bar_w}" height="10" rx="5"/></clipPath>
<g clip-path="url(#r)">{''.join(bar)}</g>
{''.join(legend)}
{''.join(rows)}
</svg>
"""


main()
