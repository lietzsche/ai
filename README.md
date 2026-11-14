# ai

AI 스킬과 CLI 명령어를 모으고 설명하는 저장소입니다. 작업 규칙은 [AGENTS.md](AGENTS.md)에 있고, Claude Code는 [CLAUDE.md](CLAUDE.md)를 통해 같은 규칙을 읽습니다.

## 시작: find-skills

모든 스킬은 Vercel의 [find-skills](https://github.com/vercel-labs/skills/tree/main/skills/find-skills)에서 시작합니다. 설치 방법과 사용법은 [docs/find-skills-guide.html](docs/find-skills-guide.html)에 정리했습니다.

```bash
# 프로젝트에 Claude Code·Codex용으로 설치 (Node.js 22.20 이상)
npx skills add vercel-labs/skills --skill find-skills -a claude-code -a codex
```

설치한 뒤에는 에이전트에게 말로 요청하거나 슬래시 명령으로 부릅니다.

```text
PR 리뷰를 도와줄 스킬이 있는지 찾아줘     # 일반 대화 (자동 선택)
/find-skills PR 리뷰                     # Claude Code
$find-skills PR 리뷰                     # Codex (/skills 목록에서도 선택 가능)
```

## 설치한 스킬

| 스킬 | 출처 | 라이선스 |
| --- | --- | --- |
| [find-skills](.agents/skills/find-skills/SKILL.md) | [vercel-labs/skills](https://github.com/vercel-labs/skills) | MIT |

새 스킬을 설치하면 이 표와 [docs/find-skills-guide.html](docs/find-skills-guide.html)의 "설치한 스킬" 섹션, [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)에 추가합니다.

## CLI 명령어 설명서

| 문서 | 대상 |
| --- | --- |
| [linux-cli-guide.html](docs/linux-cli-guide.html) | 리눅스(Ubuntu, bash) 명령어와 윈도우 대응 명령 |
| [windows-powershell-cli-guide.html](docs/windows-powershell-cli-guide.html) | Windows PowerShell |
| [claude-code-cli-guide.html](docs/claude-code-cli-guide.html) | Claude Code CLI |
| [codex-cli-guide.html](docs/codex-cli-guide.html) | Codex CLI |
| [antigravity-cli-skills.html](docs/antigravity-cli-skills.html) | Antigravity CLI 스킬과 슬래시 명령 |

HTML 파일은 브라우저로 엽니다. 리눅스에서는 `xdg-open docs/linux-cli-guide.html`, 윈도우에서는 `start docs\linux-cli-guide.html`을 씁니다.
