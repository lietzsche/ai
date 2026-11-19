# ai

AI 스킬과 CLI 명령어를 모으고 설명하는 저장소입니다. 공통 작업 규칙은 [AGENTS.md](AGENTS.md)에 있고, [CLAUDE.md](CLAUDE.md)는 같은 규칙을 연결합니다.

## 통합 설명서

| 문서 | 내용 |
| --- | --- |
| [스킬 통합 가이드](docs/skills-guide.html) | 설치된 모든 스킬의 출처·설치·호출·사용법, skills CLI, 오픈소스 참고 자료 |
| [CLI 통합 가이드](docs/cli-guide.html) | Linux·Bash와 Windows PowerShell의 명령·검색·상세 설명 |

각 분야는 위 HTML 한 파일에 모읍니다. AI 도구의 CLI 설명은 현재 범위에서 제외합니다. HTML을 내려받아 브라우저로 열어도 외부 라이브러리 없이 동작합니다.

## WSL 도구 설치

저장소 루트의 [install.sh](install.sh)로 WSL에서 `wslview`를 설치할 수 있습니다.

```bash
./install.sh          # 기본: wslview 설치
./install.sh wslview  # 설치 대상을 명시
./install.sh --help   # 도움말
wslview docs/cli-guide.html
```

Ubuntu·Debian 등 APT 기반 WSL에서 현재 설정된 저장소의 `wslu` 패키지를 설치합니다. 이미 `wslview`가 있으면 건너뜁니다. 일반 사용자로 실행하면 패키지 목록 갱신·설치에 `sudo`를 사용하며, 암호와 APT 설치 확인을 요청할 수 있습니다. 셸 설정이나 기본 브라우저 설정은 변경하지 않습니다.

현재 저장소에 `wslu`가 없으면 안내와 함께 종료합니다. Ubuntu의 `universe` 또는 배포판별 추가 저장소가 필요할 수 있으며, 저장소는 자동으로 추가하지 않습니다. [wslu 공식 설치 안내](https://wslutiliti.es/wslu/install.html)와 [Ubuntu 24.04 패키지 정보](https://packages.ubuntu.com/noble/wslu)를 참고하세요. 확인일: 2026-11-17.

## 설치한 스킬

| 스킬 | 출처 | 라이선스 |
| --- | --- | --- |
| [deep-research](.agents/skills/deep-research/SKILL.md) | [samber/cc-skills](https://github.com/samber/cc-skills) | MIT |
| [docfig](.agents/skills/docfig/SKILL.md) | 자체 작성 (git `13b0dfd` 복원) | - |
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

### 딥리서치: deep-research

Claude Code에서는 `/deep-research`, Codex에서는 `$deep-research` 또는 `/skills`로 선택해 조사 주제를 전달합니다. 여러 출처를 교차 검증하고 신뢰도와 출처 URL을 붙인 Markdown 보고서를 만듭니다. 별도 API 키 없이 기본 웹 검색을 쓰지만 서브에이전트를 많이 띄워 사용량이 큽니다. 실제 호출과 보고서 생성은 아직 검증하지 않았습니다.

### 문서 인라인 SVG·연결도 그림: docfig

Claude Code에서는 `/docfig`, Codex에서는 `$docfig` 또는 `/skills`로 선택해 대상 HTML 문서와 그릴 구조(흐름도·구조도·매핑 격자·다단 표/열 연결도)를 전달합니다. 보조 스크립트 `.agents/skills/docfig/scripts/figlib.py`(`Flow`, `matrix`, `lineage`, `tab_wrap`)와 참조 문서 `.agents/skills/docfig/references/lineage.md`로 외부 의존성 없는 그림과 점진적 노출 연결도를 삽입하고 밝은·어두운 화면, 역방향 간선, 접근성·링크를 점검합니다. 실제 클라이언트 호출은 아직 검증하지 않았습니다.
