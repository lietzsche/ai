# ai

AI로 할 수 있는 일을 재사용 가능한 스킬과 워크플로로 모으는 저장소입니다.

## 스킬

| 스킬 | 용도 |
| --- | --- |
| [grill-me](skills/grill-me/SKILL.md) | 한 번에 한 질문씩 인터뷰하여 아이디어를 목표·범위·제약·완료 기준으로 정리 |

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

이 저장소는 별도 CLI 프로그램을 설치하지 않습니다. `/grill-me` 문구를 에이전트에게 전달할 수 있는 환경에서는 `AGENTS.md`가 해당 요청을 스킬로 연결합니다. 클라이언트가 알 수 없는 슬래시 명령을 차단하면 위의 일반 문장으로 요청하세요.

## Claude Code에서 사용하기

`CLAUDE.md`가 `@AGENTS.md`로 공통 지침을 가져오므로 한글 커밋 메시지와 작업 완료 후 커밋·푸시 규칙도 공유합니다. `.claude/skills/grill-me/SKILL.md`는 공통 스킬 원본을 읽는 진입 파일로, Claude Code에서 다음과 같이 호출할 수 있습니다.

```text
/grill-me AI로 주간 뉴스 정리를 자동화하고 싶어
```

새 세션에서 `/grill-me`가 표시되는지 확인하세요. 지침은 에이전트의 행동을 안내하며 Git 훅처럼 커밋·푸시를 강제로 실행하지는 않습니다. 일반 Claude 웹 채팅에는 저장소 파일이 자동 적용되지 않습니다.

공식 문서: [프로젝트 지침과 AGENTS.md](https://code.claude.com/docs/en/memory#agentsmd), [Claude Code 스킬](https://code.claude.com/docs/en/skills).

참고한 기능은 [Google Antigravity의 내장 `/grill-me` 명령](https://antigravity.google/docs/commands/grill-me/)입니다.
