# Repository Guidelines

## Project Structure & Module Organization

This repository collects reusable AI skills and workflows. `README.md` describes available capabilities and usage. Each skill lives in `skills/<skill-name>/SKILL.md`; add supporting scripts, references, or assets only when the workflow needs them. There is currently no application source, build system, or automated test suite.

Host-specific entry files live in `.agents/skills/<skill-name>/SKILL.md` for Codex and `.claude/skills/<skill-name>/SKILL.md` for Claude Code. Keep workflow instructions in the shared original. Codex invokes skills with `$grill-me` or selects them through `/skills`; Claude Code uses `/grill-me`.

## Cross-Agent Compatibility

스킬이나 명령어 체인을 추가·변경할 때는 기본적으로 Codex와 Claude Code 양쪽에 적용한다. 공통 동작은 `skills/<name>/SKILL.md`에 작성하고, `.agents/skills/<name>/SKILL.md`와 `.claude/skills/<name>/SKILL.md`에는 공통 원본을 읽도록 하는 얇은 진입점을 둔다. 진입점에는 유효한 `name`, `description` frontmatter를 포함하고, 동작 지침을 복제하지 않는다.

명령어 체인은 공통 원본에 실행 순서, 단계 사이에 전달할 입력·결과, 종료 조건을 명시한다. 다른 도구의 슬래시 명령을 그대로 실행한다고 가정하지 말고, 각 단계의 스킬 파일을 읽어 수행하도록 연결한다. 특정 환경에만 있는 기능은 대체 동작이나 지원 제한을 설명한다.

`README.md`에 Codex의 `$<name>`·`/skills`와 Claude Code의 `/<name>` 사용 예를 함께 제공한다. 공통 프로젝트 규칙은 `AGENTS.md`에 유지하고 `CLAUDE.md`의 `@AGENTS.md` 연결을 보존한다. 완료 전 양쪽 진입점의 형식, 원본 경로, 체인의 참조를 검증한다. 실제 클라이언트의 스킬 발견·호출을 확인하지 못했다면 그 사실을 명시하고, 파일 생성만으로 자동완성까지 검증했다고 보고하지 않는다.

## Build, Test, and Development Commands

- `git diff --check`: check changes for whitespace errors before submitting.
- `git diff --stat`: review the scope of tracked changes.
- `git status --short`: check modified and newly added files.

No dependency installation or build command is required for the current Markdown content. Document runnable commands and their prerequisites alongside any future executable tools.

## Coding Style & Naming Conventions

Use Markdown headings and concise, actionable instructions. Use lowercase, hyphen-separated skill directory names, such as `grill-me`. Each `SKILL.md` must start with YAML frontmatter containing `name` and `description`. Use two spaces for YAML indentation. Keep reusable instructions in the skill rather than duplicating them across guides. Korean is appropriate for user-facing documentation; follow the user's language during conversations.

## Testing Guidelines

For documentation changes, check links, paths, examples, frontmatter, and `git diff --check`. Exercise skill behavior with a realistic request: verify question sequencing, handling of unknown answers, and the final deliverable. Do not claim automated coverage or successful runtime tests when none exist.

## Commit & Pull Request Guidelines

작업 단위가 완료되고 관련 검증을 통과하면 해당 작업의 변경 사항을 커밋하고 현재 브랜치를 원격 저장소에 푸시한다. 커밋 제목은 변경 내용을 설명하는 짧은 한글 문장으로 작성한다. 예: `요구사항 인터뷰 스킬 추가`, `클로드 공통 지침 연결`. 파일을 수정할 때마다 커밋하지 않으며, 변경이 없는 조사·질의 응답에는 빈 커밋을 만들지 않는다.

커밋 전에 diff를 확인하고 작업에 해당하는 파일만 명시적으로 스테이징한다. 사용자나 다른 작업의 변경, 비밀 정보는 포함하지 않는다. upstream이 있으면 `git push`, 없으면 원격과 현재 브랜치를 확인한 뒤 `git push -u origin <branch>`를 사용한다. 강제 푸시나 기존 커밋 재작성은 별도 요청 없이 수행하지 않는다. 권한·인증·충돌로 실패하면 미완료 상태와 이유를 보고한다. 사용자가 커밋이나 푸시를 보류하라고 명시하면 그 요청을 우선한다.

Pull requests should explain the capability, changed files, usage examples, and validation performed. Link relevant issues when available; include screenshots only for visual changes.

## Agent-Specific Instructions

When the user requests `/grill-me`, `grill-me`, or a requirements interview, read `skills/grill-me/SKILL.md` and follow it. This routes conversational requests; it does not register a native CLI command. Resolve repository facts through inspection before asking the user. Keep interview decisions separate from assumptions, and preserve existing authorization boundaries.

When the user requests `make-plan` or an execution plan, or chooses to continue from a grill-me summary, read `skills/make-plan/SKILL.md` and follow it. A plan request does not authorize implementation.

When the user requests `skill-maker`, `/skill-maker`, or asks to create, port, or update a skill in this repository, read `skills/skill-maker/SKILL.md` and follow it.

When the user requests `boost`, `/boost`, or multi-hypothesis deep reasoning on a complex bug or optimization task, read `skills/boost/SKILL.md` and follow it.
