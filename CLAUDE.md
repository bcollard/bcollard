# CLAUDE.md

This repo is the GitHub **profile README** rendered at <https://github.com/bcollard>.
The remote is `bcollard/bcollard` (GitHub requires that name); the local
directory is `github-profile`.

Read `MAINTAINING.md` before changing anything — it explains the pipeline. The
short version and the traps:

## Never hand-edit a generated region

Anything between `<!-- profile:begin:NAME -->` and `<!-- profile:end:NAME -->`
in `README.md` is overwritten by `make render`. Editing it there looks like it
worked and is silently lost on the next run.

Generated: `toolbelt`, `taps`, `upstream`, `writing`, `talks`.
To change them, edit `config/profile.toml` and run `make refresh`.

Hand-written and safe to edit directly: the header, the intro, the featured
project cards, the tech badges, the footer.

`assets/*.svg` are generated too (`scripts/make_cards.py`) — edit the generator,
not the SVGs.

## Workflow

```
make refresh   # collect → render → report drift
make check     # every link resolves, every local asset exists
make publish   # commit + push
```

Always `make check` before publishing. It exists because a broken link on this
page is the one defect readers actually notice.

## The blog is a second, read-only checkout

`scripts/collect_blog.py` reads the Hugo site at `../blog` (a separate git repo,
added as a working directory). **Never write to it from this repo's tasks.**
Use absolute paths in shell commands — the working directory persists between
commands, and a relative `cat >` has already clobbered a file in the blog repo
once.

## Conventions decided and worth keeping

- Card and table links are labelled **`website`** — not "site", "demo", or the
  name of the host. A store listing goes on the card's meta line instead.
- `bcollard/keycloak-cloudrun` is a **private** repo. It had a featured card with
  a deliberately unlinked title until `klimax-ui` took that tile. If it is ever
  featured again, leave the title unlinked — the URL 404s for every visitor
  until the repo is made public.
- Stats come from our own generated SVGs. Do not reintroduce
  `github-readme-stats.vercel.app` — its shared instance returns
  `DEPLOYMENT_PAUSED` and broke these cards before.
