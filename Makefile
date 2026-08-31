# GitHub profile README — collect, render, verify, publish.
#
#   make refresh   pull fresh data, regenerate the marked regions, report drift
#   make check     verify every link in README.md resolves
#   make publish   commit and push to github.com/bcollard/bcollard
#
# Override the blog checkout with:  make refresh BLOG_DIR=/path/to/blog

PYTHON  ?= python3
SCRIPTS := scripts
DATA    := data
ARGS    ?=

export BLOG_DIR

GITHUB_JSON := $(DATA)/github.json
BLOG_JSON   := $(DATA)/blog.json

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@echo "GitHub profile README"
	@echo
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'
	@echo
	@echo "  Variables:  BLOG_DIR=<path>   ARGS=<extra flags for report>"

# --- data collection ------------------------------------------------------

$(GITHUB_JSON): $(SCRIPTS)/collect_github.py $(SCRIPTS)/lib.py config/profile.toml
	@$(PYTHON) $(SCRIPTS)/collect_github.py > /dev/null

$(BLOG_JSON): $(SCRIPTS)/collect_blog.py $(SCRIPTS)/lib.py config/profile.toml
	@$(PYTHON) $(SCRIPTS)/collect_blog.py > /dev/null

.PHONY: data
data: $(GITHUB_JSON) $(BLOG_JSON) ## Collect GitHub + blog data into data/ (cached)

.PHONY: pull
pull: ## Force a fresh collection, ignoring the cache
	@$(PYTHON) $(SCRIPTS)/collect_github.py > /dev/null
	@$(PYTHON) $(SCRIPTS)/collect_blog.py > /dev/null

# --- rendering ------------------------------------------------------------

.PHONY: render
render: data ## Regenerate the marked regions of README.md
	@$(PYTHON) $(SCRIPTS)/render.py > /dev/null

.PHONY: refresh
refresh: pull render report ## Pull fresh data, render, then report drift

# --- verification ---------------------------------------------------------

.PHONY: check
check: ## Verify every link in README.md resolves
	@$(PYTHON) $(SCRIPTS)/check_links.py

.PHONY: report
report: data ## What's new on GitHub/the blog that the README misses
	@$(PYTHON) $(SCRIPTS)/report.py $(ARGS)

.PHONY: diff
diff: ## Show uncommitted README changes
	@git diff -- README.md || true

.PHONY: verify
verify: render check ## Render, then check links — run before publishing

# --- publishing -----------------------------------------------------------

.PHONY: publish
publish: ## Commit and push README.md to the profile repo
	@git diff --quiet -- README.md config Makefile scripts && \
	  git diff --cached --quiet -- README.md config Makefile scripts && \
	  { echo "nothing to publish"; exit 0; } || true
	@git add README.md config Makefile scripts .gitignore MAINTAINING.md
	@git commit -m "profile: refresh from GitHub + blog data" \
	  -m "Regenerated with \`make refresh\`."
	@git push
	@echo "pushed → https://github.com/bcollard"

# --- housekeeping ---------------------------------------------------------

.PHONY: clean
clean: ## Remove collected data
	@rm -rf $(DATA) $(SCRIPTS)/__pycache__
	@echo "cleaned"
