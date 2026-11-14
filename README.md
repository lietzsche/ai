# ai

AI 스킬과 CLI 명령어를 모으고 설명하는 저장소입니다. 공통 작업 규칙은 [AGENTS.md](AGENTS.md)에 있고, [CLAUDE.md](CLAUDE.md)는 같은 규칙을 연결합니다.

## 통합 설명서

| 문서 | 내용 |
| --- | --- |
| [스킬 통합 가이드](docs/skills-guide.html) | 설치된 모든 스킬의 출처·설치·호출·사용법, skills CLI, 오픈소스 참고 자료 |
| [CLI 통합 가이드](docs/cli-guide.html) | Linux·Bash와 Windows PowerShell의 명령·검색·상세 설명 |

각 분야는 위 HTML 한 파일에 모읍니다. AI 도구의 CLI 설명은 현재 범위에서 제외합니다. HTML을 내려받아 브라우저로 열어도 외부 라이브러리 없이 동작합니다.

## 설치한 스킬

| 스킬 | 출처 | 라이선스 |
| --- | --- | --- |
| [find-skills](.agents/skills/find-skills/SKILL.md) | [vercel-labs/skills](https://github.com/vercel-labs/skills) | MIT |
| [handoff](.agents/skills/handoff/SKILL.md) | [mattpocock/skills](https://github.com/mattpocock/skills) | MIT |
| [visual-explainer](.agents/skills/visual-explainer/SKILL.md) | [nicobailon/visual-explainer](https://github.com/nicobailon/visual-explainer) | MIT |

새 스킬은 find-skills로 찾고 프로젝트 범위로 양쪽 에이전트에 설치합니다. 설치한 모든 스킬은 [스킬 통합 가이드](docs/skills-guide.html#installed)와 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 기록합니다.

```bash
# Node.js 22.20 이상
npx skills add <owner/repo> --skill <name> -a claude-code -a codex
```

```text
/find-skills PR 리뷰                     # Claude Code
$find-skills PR 리뷰                     # Codex (/skills에서도 선택)
/handoff 다음 세션에서 로그인 오류 수정  # Claude Code
$handoff 다음 세션에서 로그인 오류 수정  # Codex
```

설치 원본은 `.agents/skills/<name>/`, Claude Code 연결은 `.claude/skills/<name>`에 있습니다. handoff는 인계서를 OS 임시 폴더에 저장하며 자동 재개 훅은 없습니다. 실제 클라이언트에서 모든 스킬의 발견·호출·자동완성까지 검증한 것은 아닙니다.

### 그림 중심 HTML: visual-explainer

Claude Code에서는 `/visual-explainer`, Codex에서는 `$visual-explainer` 또는 `/skills`로 선택해 주제와 저장 경로를 전달합니다. 예: “캐시 동작을 SVG 흐름도와 수치 차트 중심으로 HTML에 정리해 줘.” 번들 Node.js 렌더러를 사용하며 일부 차트는 CDN 라이브러리를 쓸 수 있습니다. 오프라인 문서는 외부 라이브러리·웹폰트 없이 만들어 달라고 명시하세요. 실제 클라이언트 호출과 문서 생성 동작은 아직 검증하지 않았습니다.
