# Repository Guidelines

## Project Structure & Module Organization

This repository collects reusable AI skills and workflows. `README.md` describes available capabilities and usage. Each skill lives in `skills/<skill-name>/SKILL.md`; add supporting scripts, references, or assets only when the workflow needs them. There is currently no application source, build system, or automated test suite.

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
