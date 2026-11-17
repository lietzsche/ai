#!/usr/bin/env bash
# WSL의 현재 APT 저장소에서 wslview(wslu)를 설치한다.
set -euo pipefail

usage() {
    cat <<'EOF'
사용법: ./install.sh [wslview] | --help

WSL의 Ubuntu·Debian 등 APT 환경에서 wslview를 설치합니다.
인자를 생략하면 wslview를 설치합니다. 이미 설치되어 있으면 건너뜁니다.
패키지 설치 시 sudo 암호와 APT의 설치 확인을 요청할 수 있습니다.
EOF
}

fail() {
    printf '오류: %s\n' "$*" >&2
    exit 1
}

if [[ $# -gt 1 ]]; then
    usage >&2
    exit 2
fi
case "${1:-wslview}" in
    -h|--help) usage; exit 0 ;;
    wslview) ;;
    *) usage >&2; exit 2 ;;
esac

if [[ ! -r /proc/sys/kernel/osrelease ]]; then
    fail 'WSL 환경에서 실행해 주세요.'
fi
kernel_release=$(</proc/sys/kernel/osrelease)
if [[ ${kernel_release,,} != *microsoft* && ${kernel_release,,} != *wsl* ]]; then
    fail 'WSL 환경에서 실행해 주세요.'
fi

if command -v wslview >/dev/null 2>&1; then
    printf 'wslview가 이미 설치되어 있습니다: %s\n' "$(command -v wslview)"
    exit 0
fi

command -v apt-get >/dev/null 2>&1 || fail '현재는 APT 기반 WSL 배포판만 지원합니다. https://wslutiliti.es/wslu/install.html 을 참고하세요.'
command -v apt-cache >/dev/null 2>&1 || fail 'apt-cache 명령을 찾을 수 없습니다.'

privilege=()
if (( EUID != 0 )); then
    command -v sudo >/dev/null 2>&1 || fail 'sudo를 설치하거나 root로 실행해 주세요.'
    privilege=(sudo)
fi

printf 'APT 패키지 목록을 갱신합니다.\n'
"${privilege[@]}" apt-get update
if ! apt-cache show wslu >/dev/null 2>&1; then
    fail '현재 APT 저장소에 wslu가 없습니다. 배포판에 맞는 저장소를 설정한 뒤 다시 실행하세요: https://wslutiliti.es/wslu/install.html'
fi
printf 'wslview가 포함된 wslu 패키지를 설치합니다.\n'
"${privilege[@]}" apt-get install wslu
command -v wslview >/dev/null 2>&1 || fail '설치 후 wslview를 찾을 수 없습니다. PATH와 패키지 설치 결과를 확인하세요.'
printf '설치 완료: %s\n' "$(command -v wslview)"
printf '사용 예: wslview docs/cli-guide.html\n'
