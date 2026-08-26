# Operator Workflow

From topic to published master. Draft mode runs fully offline; production mode uses
your configured providers.

## 0. One-time setup

```bash
make install
zkid init-series --name "Mimi's Little World"     # writes templates/series-bible.json
# edit templates/series-bible.json and templates/characters/*.json to taste
```

## 1. Story (GATE 1)

```bash
zkid story --topic "Mimi finds a red apple" --ep EP001 --offline
zkid gates status --ep EP001
# review episodes/ep001/metadata/episode.json, then:
zkid gates approve --gate 1 --ep EP001 --note "story reviewed"
```

In `--draft` produce runs, gates 1-2 are auto-approved (see `config/factory.yaml`).

## 2. Characters + storyboard (GATE 2)

```bash
zkid storyboard --ep EP001          # shot breakdown + scene manifest + reference sheets
zkid gates approve --gate 2 --ep EP001 --note "boards look right"
```

## 3. Scene generation (GATE 3)

```bash
zkid voice --ep EP001
zkid stills --ep EP001              # image QC before any video spend
zkid videos --ep EP002              # queue + retry ladder + budget enforcement
zkid gates status --ep EP001        # GATE 3 set by system-qc when all jobs APPROVED
```

Anything that exhausts retries lands in `MANUAL_REVIEW`; inspect with `zkid status`.

## 4. Assembly + final QC (GATE 4)

```bash
zkid assemble --ep EP001            # timeline → conform → concat → mix → subtitles → render
zkid qc --ep EP001                  # re-run automated QC any time
```

## 5. Human publish approval (GATE 5 — never automatic)

```bash
zkid gates approve --gate 5 --ep EP001 --note "watched end-to-end, safe for kids"
zkid publish-package --ep EP001     # requires GATE 5 approved
```

The package in `episodes/<ep>/output/publish-package/` contains video.mp4,
subtitles.srt, thumbnail.png and metadata.json (made_for_kids: true).

## Full-loop shortcuts

```bash
zkid produce --topic "..." --ep EP001 --draft  --auto-approve   # offline draft
zkid produce --topic "..." --ep EP002 --production              # real providers, gates enforced
```

## Monitoring

```bash
zkid status --ep EP001      # job states, budget usage, renders, gate checklist
sqlite3 factory.db 'select state,count(*) from generation_jobs group by state;'
```

## Cost discipline

Budgets live in `config/factory.yaml` (`budgets:`). Every generation charges the
episode budget before spend; exceeding a limit raises `BudgetExceeded` instead of
silently burning quota. Draft mode is always free (placeholder engines).
