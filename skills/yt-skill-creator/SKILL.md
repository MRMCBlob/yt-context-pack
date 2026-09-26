---
name: yt-skill-creator
description: >-
  Creates a reusable agent skill from one or more YouTube videos. Use when the
  user says things like "create a skill from these YouTube videos", "turn this
  video into a skill", or invokes /yt-skill-creator with YouTube URLs. Distills
  the repeatable technique demonstrated in the videos into a SKILL.md following
  skill-authoring best practices. Not for summarizing or researching videos —
  that is yt-context-pack.
---

# YouTube Skill Creator

Turns videos into skills: build context packs for each URL, distill the
shared repeatable procedure, scaffold a skill another agent can execute.

## Workflow

1. **Scope** — ask (once, briefly) if unclear: what should the skill do, who
   triggers it, any tool constraints. With 3+ URLs at ≥30 min each, confirm
   before transcribing everything (slow on CPU; suggest `YT_PACK_MODEL=base`).
2. **Pack every video** — invoke the `yt-context-pack` skill (or run its
   `scripts/build_pack.py "<url>"`, then read artifacts per that skill's
   workflow). One pack per URL. Skip claims/comment sections irrelevant to
   skill extraction.
3. **Distill** — across packs, extract:
   - The repeatable procedure: steps, decision points, failure modes the
     creator demonstrates. Prefer their explicit "do this, not that" moments.
   - Tools/commands they use (name exact ones; viewers correct details in
     the comment pulse — trust corrections over the video).
   - Disagreements between videos → note as options in the skill, or pick
     the one with better comment consensus.
   - Skip everything non-repeatable (anecdotes, sponsor reads, one-offs).
4. **Scaffold** the skill (skill-creator conventions):
   - `<name>/SKILL.md` — frontmatter: `name` (kebab-case = dir name) +
     `description` (what it does AND when to trigger; this is the only
     trigger mechanism — put all "when to use" here). Body: imperative,
     under ~100 lines, steps the demoing creator actually performs.
   - `references/` only for detail the body shouldn't always load (exact
     parameters, checklists, examples from the videos with [M:SS] cites).
   - `scripts/` only when a step needs deterministic reliability.
   - Nothing else — no README, no changelog.
5. **Validate**:
   - Frontmatter parses as YAML (`yaml.safe_load`), name matches dir name.
   - Run any script once (`doctor`-style dry run at minimum).
   - Body references every bundled file, and every referenced file exists.
6. **Install + iterate** — copy into `~/.claude/skills/<name>/` (or
   `npx skills add <path>`), run it once on a real task from the videos,
   fix what struggles, re-test. Report: skill path + one-line trigger test.

## Judgment

- Videos teach *how someone works*, not facts. Extract procedure, not lore.
- A skill that only paraphrases the video is a failure — it must be
  executable without watching anything.
- One technique across many videos > shallow survey of many techniques.
  If videos diverge, ask the user which thread to follow.
