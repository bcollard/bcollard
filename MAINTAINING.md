# Maintaining this profile

The README is part hand-written, part generated. Prose you'd want to word
carefully stays yours; lists that go stale on their own are regenerated from
live data.

```
make refresh     # pull GitHub + blog data, regenerate, then report drift
make check       # every link in README.md still resolves
make publish     # commit + push
```

## How it fits together

```
config/profile.toml ──┐
                      ├──► scripts/render.py ──► README.md  (marked regions only)
data/github.json ─────┤
data/blog.json    ────┘
        ▲
        └── scripts/collect_github.py  (gh CLI: repos, PRs, issues, taps, stats)
            scripts/collect_blog.py    (Hugo content/: posts, talks, side projects)
```

`data/` is generated and gitignored. `make data` caches it; `make pull` forces
a refetch.

## What is generated vs. hand-written

Generated regions are delimited in `README.md`:

```markdown
<!-- profile:begin:upstream -->
...anything here is overwritten by `make render`...
<!-- profile:end:upstream -->
```

| Region | Source |
|---|---|
| `toolbelt` | `[[toolbelt]]` blurbs in the config; repo URL, language and site pulled live |
| `taps` | every public non-fork `homebrew-*` repo you own |
| `upstream` | `gh search prs`, minus your own repos and `upstream.exclude`; ordered by `upstream.order`, described by `upstream.highlight`, everything else rolled into a trailing line |
| `writing` | `[[writing]]` slugs; titles and URLs come from the blog's front matter |
| `talks` | `talks.slugs`; titles and dates come from `content/other/` |

**Hand-written:** the header, the intro paragraph, the four featured project
cards, the tech badges and the footer. Edit those in `README.md` directly —
`make render` will not touch them.

The featured cards are deliberately manual: they carry the *why* of each
project, and a generator would flatten that into a description field. The
`featured = [...]` list in the config exists only so `make report` can tell you
when one of them is renamed, archived or made private.

## Routine changes

| You want to… | Do this |
|---|---|
| Add a CLI to the toolbelt | Append a `[[toolbelt]]` block, `make refresh` |
| Feature a new project | Write the card in `README.md`, add its name to `featured` |
| Credit a new upstream repo | Add it to `upstream.order` + an `[[upstream.highlight]]`, `make refresh` |
| Hide a drive-by PR | Add the repo to `upstream.exclude` |
| Link a new post | Append a `[[writing]]` block with its `slug` |
| Add a talk | Append the slug to `talks.slugs` |
| Silence a repo in the report | Add its name to `github.exclude` |

`{stars:repo-name}` inside a `writing` note expands to that repo's live star
count, so `⭐30` never goes stale.

## `make report`

Read-only. It diffs the live world against what the README actually says and
prints what it finds:

- featured repos that were renamed, archived or made private
- public repos with traction that the README never mentions
- upstream repos you contributed to but don't credit
- side projects on the blog's page but missing here (and the reverse)
- recent posts not linked, and linked posts still marked `draft` — those 404
- empty GitHub sidebar fields (`bio`, `company`) that no README can fill

Unstarred repos untouched for 3+ years are collapsed; `make report ARGS=--all`
lists them.

## Requirements

`gh` (authenticated), Python 3.11+ (stdlib only — `tomllib`), GNU Make. The
blog checkout is expected at `../blog`; override with `BLOG_DIR=/path make …`.
