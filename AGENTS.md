# Repository Guidelines

## 프로젝트 목적

이 저장소는 AI 스킬과 CLI 명령어를 모으고 설명하는 프로젝트다. 결과물은 두 가지다.

- **AI 스킬 모음과 설명서**: 에이전트에 설치한 스킬과, 그 스킬의 설치·사용법을 설명하는 HTML 문서
- **CLI 명령어 설명서**: 도구·셸별 명령어를 공식 문서 기준으로 정리한 HTML 문서

모든 스킬은 Vercel의 `find-skills`에서 시작한다. 필요한 기능이 생기면 `find-skills`로 스킬을 찾아 설치하고, 설치한 스킬을 문서에 추가한다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `.agents/skills/<name>/` | 설치한 스킬의 원본. Codex 등 `.agents/skills`를 읽는 에이전트가 사용 |
| `.claude/skills/<name>` | Claude Code용. `.agents/skills/<name>`을 가리키는 심볼릭 링크 |
| `docs/find-skills-guide.html` | `find-skills` 설치·사용법과 이 저장소에 설치한 스킬 설명 |
| `docs/<대상>-cli-guide.html` | CLI 명령어 설명서 (예: `linux-cli-guide.html`) |
| `THIRD_PARTY_NOTICES.md` | 외부 스킬의 출처·커밋·라이선스 |

## 스킬 설치와 문서화

1. 새 스킬은 `find-skills`로 찾는다. 설치 전에 설치 수, 출처 신뢰도, 저장소 스타, 라이선스를 확인한다.
2. 프로젝트 범위로 Claude Code와 Codex 양쪽에 설치한다.

   ```bash
   npx skills add <owner/repo> --skill <name> -a claude-code -a codex
   ```

   CLI가 `skills-lock.json`을 만들거나 갱신하면 함께 커밋한다. `skills` CLI는 Node.js 22.20 이상이 필요하다.
3. 설치한 스킬 파일은 직접 고치지 않는다. 바꿀 일이 있으면 `npx skills update`나 재설치로 처리한다.
4. `THIRD_PARTY_NOTICES.md`에 출처 URL, 커밋, 라이선스를 기록한다.
5. `docs/find-skills-guide.html`의 "설치한 스킬" 섹션에 스킬별 카드를 추가한다. 이름, 출처, 라이선스, 설치 명령, 용도, 사용 예를 적는다.
6. 스킬별 탭 구성은 이후 문서 관련 스킬로 만들 예정이다. 그 전까지는 탭을 미리 만들지 않고 카드만 추가한다.

## CLI 명령어 설명서

- 파일은 `docs/<대상-slug>-cli-guide.html`에 둔다. slug는 소문자와 하이픈으로 만든다.
- 양식은 기존 설명서(`docs/linux-cli-guide.html`)를 따른다. 구성은 다크 테마 단일 HTML, 핵심 명령 카드, 검색 가능한 전체 명령 표, 행 클릭 시 펼쳐지는 상세 설명이다. 외부 라이브러리와 웹폰트는 쓰지 않는다.
- 공식 문서, `--help`, `man`을 1차 출처로 삼는다. 확인하지 못한 항목은 "미확인"으로 표시하고, 옵션이나 동작을 지어내지 않는다.
- 조사일과 출처 링크를 문서에 남긴다.

## 검증

- `git status --short`, `git diff --stat`, `git diff --check`로 범위와 공백 오류를 확인한다.
- HTML은 목차 앵커, 링크, 한글 깨짐, 스크립트 오류를 확인한다. 브라우저로 직접 확인하지 못했다면 그 사실을 보고한다.
- 클라이언트에서 스킬이 실제로 발견·호출되는지 확인하지 못했다면, 파일 배치만으로 동작을 확인했다고 보고하지 않는다.

## 커밋과 푸시

작업 단위가 끝나고 검증을 통과하면 해당 변경만 명시적으로 스테이징해 커밋하고 현재 브랜치를 푸시한다. 커밋 제목은 변경 내용을 설명하는 짧은 한글 문장으로 쓴다. 비밀 정보와 다른 작업의 변경은 포함하지 않는다. 강제 푸시나 기존 커밋 재작성은 요청 없이 하지 않는다. 사용자가 커밋이나 푸시를 보류하라고 하면 그 요청을 따른다.

## Windows 브라우저 자동화

Windows Chrome·Edge를 새 임시 프로필로 반복 실행하면 OS 계정이 잠길 수 있다. WSL이나 Git Bash에서 Lighthouse·Puppeteer·Playwright·스크린샷 도구로 Windows 브라우저를 실행할 때도 마찬가지다. 측정 전용 고정 프로필을 쓰고, 같은 프로필은 직렬로만 사용한다. 이 규칙은 서브에이전트에도 전달한다. 안전한 실행 경로가 없으면 임시 프로필로 우회하지 말고 미측정으로 남긴다.

## 대화

사용자의 언어(기본 한국어)로 대화하고 문서를 작성한다.
