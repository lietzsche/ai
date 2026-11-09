# ai

AI로 할 수 있는 일을 재사용 가능한 스킬과 워크플로로 모으는 저장소입니다.

## 스킬

| 스킬 | 용도 |
| --- | --- |
| [grill-me](skills/grill-me/SKILL.md) | 한 번에 한 질문씩 인터뷰하여 아이디어를 목표·범위·제약·완료 기준으로 정리 |
| [make-plan](skills/make-plan/SKILL.md) | 확정된 요구사항을 단계·산출물·검증·위험이 담긴 실행 계획으로 정리 |
| [cli-guide](skills/cli-guide/SKILL.md) | 특정 CLI의 명령어를 공식 문서 기준으로 조사해 검색·펼쳐보기가 있는 단일 HTML 설명서로 정리 |

## 인터뷰 사용하기

### Codex CLI / IDE 확장

이 저장소를 연 상태에서 `/skills`로 `grill-me`가 있는지 확인하거나 `$`를 입력해 선택합니다.

```text
$grill-me AI로 주간 뉴스 정리를 자동화하고 싶어
```

Codex용 진입 파일은 `.agents/skills/grill-me/SKILL.md`입니다. 목록이 갱신되지 않으면 Codex를 재시작하세요. `/grill-me`는 Codex의 등록된 슬래시 명령이 아닙니다. [공식 스킬 문서](https://learn.chatgpt.com/docs/build-skills)

### 일반 대화로 요청하기

이 저장소의 `AGENTS.md`를 읽는 에이전트에게 다음처럼 요청합니다.

```text
grill-me: AI로 매주 업계 뉴스를 정리하고 싶은데, 질문하면서 원하는 걸 정리해 줘.
```

에이전트가 지침을 자동으로 읽지 않는 환경에서는 파일을 직접 지정합니다.

```text
skills/grill-me/SKILL.md를 읽고 내 아이디어를 인터뷰해 줘: 개인 지출 관리 자동화
```

질문에는 추천 선택지가 함께 나오며 자유롭게 답하거나 모르는 항목을 건너뛸 수 있습니다. 마지막에는 확정 사항과 미정 사항을 구분한 요구사항 요약을 받습니다. 파일로 남기려면 저장 경로를 함께 요청하세요.

선택지는 Codex의 `request_user_input` 또는 `request_user_input_async`, Claude Code의 `AskUserQuestion`을 우선 사용해 제시합니다. 버튼·카드·터미널 선택 목록 등 실제 모양은 클라이언트에 따라 다릅니다. 현재 환경이나 모드에서 질문 도구를 사용할 수 없으면 이유를 알리고 번호 목록으로 질문합니다. Codex에서는 `/plan`으로 계획 모드에 들어간 뒤 `$grill-me`를 호출하는 방법도 있습니다. 답변 없이 추천안을 확정하지 않습니다.

이 저장소는 별도 CLI 프로그램을 설치하지 않습니다. `/grill-me` 문구를 에이전트에게 전달할 수 있는 환경에서는 `AGENTS.md`가 해당 요청을 스킬로 연결합니다. 클라이언트가 알 수 없는 슬래시 명령을 차단하면 위의 일반 문장으로 요청하세요.

## 실행 계획 만들기

인터뷰 요약을 제시한 뒤 grill-me가 실행 계획으로 이어갈지 묻습니다. 이어가기를 선택하면 확인한 요약을 입력으로 `make-plan` 지침에 따라 계획을 작성합니다. 요약 수정이나 요약으로 마치기도 선택할 수 있으며, 답변 없이 계획으로 넘어가지 않습니다.

`make-plan`은 단독으로도 호출할 수 있습니다. 계획은 단계별 산출물·확인 방법, 전체 검증, 위험과 대응, 가정으로 구성되며, 저장소 작업이면 변경할 파일과 검증 명령을 추가합니다. 계획은 대화로 제시하고, 저장 경로를 지정한 경우에만 파일로 씁니다. 계획 작성은 구현 승인이 아닙니다.

```text
$make-plan 사내 위키의 오래된 문서를 매달 점검하는 자동화를 만들고 싶어
```

```text
/make-plan 사내 위키의 오래된 문서를 매달 점검하는 자동화를 만들고 싶어
```

위는 Codex(`$`나 `/skills`로 선택), 아래는 Claude Code 예시입니다. Codex용 진입 파일은 `.agents/skills/make-plan/SKILL.md`, Claude Code용은 `.claude/skills/make-plan/SKILL.md`입니다.

## CLI 명령어 설명서 만들기

`cli-guide`는 지정한 도구의 명령어를 조사해 [docs/antigravity-cli-skills.html](docs/antigravity-cli-skills.html)과 같은 양식(핵심 명령 카드, 검색 가능한 전체 명령 표, 행을 클릭하면 펼쳐지는 상세 설명)의 HTML로 만듭니다. 경로를 지정하지 않으면 `docs/<대상>-cli-guide.html`에 저장합니다.

```text
$cli-guide Linux 파일·프로세스 관리 명령어
```

```text
/cli-guide Claude Code 슬래시 명령어
```

위는 Codex(`$`나 `/skills`로 선택), 아래는 Claude Code 예시입니다. 진입 파일은 `.agents/skills/cli-guide/SKILL.md`와 `.claude/skills/cli-guide/SKILL.md`이며, 양식 견본은 `skills/cli-guide/assets/example.html`입니다.

## Claude Code에서 사용하기

`CLAUDE.md`가 `@AGENTS.md`로 공통 지침을 가져오므로 한글 커밋 메시지와 작업 완료 후 커밋·푸시 규칙도 공유합니다. `.claude/skills/grill-me/SKILL.md`는 공통 스킬 원본을 읽는 진입 파일로, Claude Code에서 다음과 같이 호출할 수 있습니다.

```text
/grill-me AI로 주간 뉴스 정리를 자동화하고 싶어
```

새 세션에서 `/grill-me`가 표시되는지 확인하세요. 지침은 에이전트의 행동을 안내하며 Git 훅처럼 커밋·푸시를 강제로 실행하지는 않습니다. 일반 Claude 웹 채팅에는 저장소 파일이 자동 적용되지 않습니다.

공식 문서: [프로젝트 지침과 AGENTS.md](https://code.claude.com/docs/en/memory#agentsmd), [Claude Code 스킬](https://code.claude.com/docs/en/skills).

참고한 기능은 [Google Antigravity의 내장 `/grill-me` 명령](https://antigravity.google/docs/commands/grill-me/)입니다.

## CLI 욜로(YOLO) 모드 명령어

도구 실행과 파일 수정을 확인 프롬프트 없이 자동 승인하는 플래그입니다. 신뢰할 수 있거나 격리된 환경에서만 사용하세요.

| 도구 | 명령어 | 비고 |
| --- | --- | --- |
| Antigravity CLI | `agy --dangerously-skip-permissions` | 샌드박스 내 자동 실행은 `agy --mode auto` |
| Claude Code | `claude --dangerously-skip-permissions` | 모든 권한 확인 생략 |
| OpenAI Codex CLI | `codex --yolo` | `--dangerously-bypass-approvals-and-sandbox` 단축 플래그 |
| Gemini CLI | `gemini --yolo` | 권장: `gemini --approval-mode=yolo` (세션 중 `Ctrl+Y`) |
