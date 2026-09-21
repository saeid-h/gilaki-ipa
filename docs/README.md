# Documentation

Operator and agent docs live under `docs/` in **three buckets**. The only Markdown file at repo root is [`README.md`](../README.md) (plus `LICENSE` when added). The only files allowed directly in `docs/` are this catalog and the legacy pointer [`PROJECT_PLAN.md`](PROJECT_PLAN.md).

If you add or rename a doc, update the table in the same change. Put the file in the matching subdirectory — never drop a new durable doc on `docs/` itself.

## Catalog

| File | Audience | What it is allowed to define |
|---|---|---|
| [`product/plan.md`](product/plan.md) | Humans + agents | Product, privacy split, locked §3, phases, tests. **Source of truth.** |
| [`product/design.md`](product/design.md) | Agents building UI | Caspian Paper tokens, type, screens. Look and feel only. |
| [`engineering/api.md`](engineering/api.md) | Clients + API work | HTTP contract. Must match FastAPI routes. |
| [`engineering/deploy.md`](engineering/deploy.md) | Operator on Linux | Clone, `scripts/start-server.sh`, venv, Nginx. |
| [`engineering/android.md`](engineering/android.md) | Android work | applicationId, storage, screens, HTTPS. |
| [`agents/cursor.md`](agents/cursor.md) | Agents | Prompt pack, one phase per chat. |
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | Old Cursor rule path | Pointer to `product/plan.md` only. |

Cursor rule (Agent leftover): `.cursor/rules/docs.mdc` always apply. Product rule: `.cursor/rules/gilaki-ipa.mdc`.

## Where a new file goes

| Topic | Subdir |
|---|---|
| Product intent, maps, phases, tests, privacy | `product/` |
| Visual system, copy decks, UX specs | `product/` |
| API, ffmpeg, start script, Nginx, Android engineering | `engineering/` |
| Agent prompt packs, Cursor workflow | `agents/` |

Do not add `docs/foo.md` at the bucket root. Do not add a fourth top-level folder without a plan revision.

## Create vs update

**Update** the file whose column matches the change: new route → `engineering/api.md`; new color → `product/design.md`; bind/script → `engineering/deploy.md` and plan §3 if locked.

**Create** a new file only if all of these are true:

1. The topic will still matter in six months
2. It does not fit an existing file
3. Distinct audience or distinct durable topic
4. It lands in `product/`, `engineering/`, or `agents/`
5. You add a row to this catalog in the same change

**Do not create:** status notes, meeting dumps, a second plan, copies of §3. History is git.

## Locked decisions

[`product/plan.md`](product/plan.md) §3 is closed. Changing a locked row requires an explicit plan revision in that file. Do not “fix” URLs only in the root README.

## Same-change rule

Behaviour change includes the matching doc in the same chat or commit.

| You changed | You also update |
|---|---|
| FastAPI routes, errors, limits | `engineering/api.md`, tests in plan §12 |
| ffmpeg / start script / Nginx / venv path | `engineering/deploy.md`, plan §10 |
| Web or Android UI | `product/design.md`; `agents/cursor.md` if the prompt pack is wrong |
| Product intent, phases, privacy | `product/plan.md` |
| Android id, storage, screens | `engineering/android.md` |

## Language and place

- Docs are English
- Paths are repo-relative
- Master plan and DESIGN.md never live at repo root
