r"""docfig: 문서(HTML)에 직접 쓰는 인라인 SVG·관계망 그림 도구. 외부 라이브러리·이미지·웹폰트 없이 오프라인·폐쇄망에서도 열린다.

쓰는 법 (그림 만드는 임시 스크립트에서):
    import sys; sys.path.insert(0, '.agents/skills/docfig/scripts')  # 또는 현재 프로젝트의 figlib.py가 있는 경로
    from figlib import Flow, compare, matrix, network, figure, Doc

    # 1) 흐름도·구조도·분기 회로도 (상자 ~12개 안팎)
    f = Flow(1000, 260, '그림이 말하는 핵심 구조 한 문장(스크린리더용)', 'dep')
    f.lane(10, 22, 280, '1단계 · 검증', '반영 전 자동 확인')
    f.card(10, 56, 180, 68, '사전점검', ['스키마·권한 확인'], tone='accent', sub='입력 확인', badge='자동')
    f.arrow([(190, 90), (248, 90)], '통과하면', 219, 80)
    svg = f.render()

    # 2) 대립·전환 대조도 (통념->재정의, 변경 전->변경 후)
    svg_cmp = compare([('기존 방식', '수동 실행·누락 위험', '자동 파이프라인', '검증 통과 시에만 반영', '규칙 코드화')],
                      '수동 절차에서 자동 검증 파이프라인으로의 전환', 'cmp')

    # 3) 2축 다대다 매핑·상관 격자
    svg_mtx = matrix([('축1', '설명')], [('묶음', [('항목', '보조설명', False, {0: ('strong', '핵심')})])],
                     '항목과 축의 상관 격자', 'mtx')

    # 4) 다층 초점 관계망 (노드 12개 이상, 여러 단계의 선행·파급 추적)
    fig_net = network(net_data, '노드를 클릭하면 선행 요인(초록)과 파급 결과(파랑)만 강조됩니다.', fid='fig-net')

    d = Doc('docs/guide.html')
    d.insert_after('<h2 id="s2">2. 구조</h2>\n', figure(svg, '그림에서 읽어야 할 핵심 요지', 'fig-arch'))
    d.save()

명령줄:
    python3 .agents/skills/docfig/scripts/figlib.py check <html>...      외부 의존성, aria-label, 글자 넘침, 역방향 간선, 깨진 링크 점검
    python3 .agents/skills/docfig/scripts/figlib.py shot <html> [폴더]    그림마다 밝은·어두운 화면 스크린샷(PNG) 생성
"""
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.parse

# ---------------------------------------------------------------- 색 (문서 CSS와 무관하게 그림 전용 변수)
LIGHT = {'text': '#1F2328', 'muted': '#5F6670', 'line': '#D3D7DC', 'panel': '#FFFFFF', 'fill': '#F3F5F7',
         'accent': '#1F5F8B', 'accent-bg': '#E8F1F7', 'warn': '#8A5A00', 'warn-bg': '#FDF3DC',
         'no': '#9B2C2C', 'no-bg': '#FBE9E9', 'ok': '#1D6B45', 'ok-bg': '#E5F3EC'}
DARK = {'text': '#E8E9EB', 'muted': '#A3A9B1', 'line': '#3A3F46', 'panel': '#1F2226', 'fill': '#262A30',
        'accent': '#8CC3E8', 'accent-bg': '#1E3442', 'warn': '#F0C674', 'warn-bg': '#3B2F14',
        'no': '#F0A0A0', 'no-bg': '#3E2020', 'ok': '#86D0A8', 'ok-bg': '#183428'}
MARK = '/* docfig */'
NET_MARK = '/* docfig-net */'
NET_SCRIPT_ID = 'docfig-net-js'


def _vars(d):
    return ';'.join(f'--fg-{k}:{v}' for k, v in d.items())


FIG_CSS = (MARK + '\n:root,[data-theme="light"]{' + _vars(LIGHT) + '}\n'
           '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){' + _vars(DARK) + '}}\n'
           ':root[data-theme="dark"],[data-theme="dark"]{' + _vars(DARK) + '}\n'
           'figure.fig{background:var(--fg-panel);color:var(--fg-text);border:1px solid var(--fg-line);border-radius:10px;padding:12px 14px;margin:14px 0;overflow-x:auto}\n'
           'figure.fig>svg{display:block;width:100%;height:auto;margin:0 auto}\n'
           'figure.fig figcaption{font-size:13px;color:var(--fg-muted);margin-top:8px;line-height:1.6}\n')

V = lambda k: f'var(--fg-{k})'  # noqa: E731


def esc(t):
    return str(t).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def unesc(t):
    return str(t).replace('&quot;', '"').replace('&gt;', '>').replace('&lt;', '<').replace('&amp;', '&')


def text_width(t, size=12.0):
    """한글·전각은 넓게, 영문·숫자는 좁게 어림한 글자 폭(px). 상자 폭·범례 간격·넘침 점검용."""
    return sum((0.95 if ord(ch) > 0x2000 else 0.56) * size for ch in str(t))


BOX = {
    'item': f'fill:{V("panel")};stroke:{V("line")};stroke-width:1.5',          # 기본 구성요소·대상
    'pii': f'fill:{V("panel")};stroke:{V("warn")};stroke-width:2.5',           # 민감정보·주의 경계
    'step': f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:1.5',   # 처리·단계·핵심 개념
    'llm': f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:3',      # 모델·판정·중추 원리
    'person': f'fill:{V("warn-bg")};stroke:{V("warn")};stroke-width:1.5',     # 사람·외부 개입·전환점
    'ok': f'fill:{V("ok-bg")};stroke:{V("ok")};stroke-width:1.5',             # 완료·도달·해법
    'gap': f'fill:{V("no-bg")};stroke:{V("no")};stroke-width:1.5;stroke-dasharray:6 4',  # 미구현·단절·방어 함정
    'group': f'fill:none;stroke:{V("line")};stroke-width:1.5',                 # 묶음 테두리
    'band': f'fill:{V("fill")};stroke:{V("line")};stroke-width:1',             # 배경 띠
}

TONE_MAP = {
    'neutral': ('muted', 'fill'), 'muted': ('muted', 'fill'), 'source': ('muted', 'fill'),
    'accent': ('accent', 'accent-bg'), 'step': ('accent', 'accent-bg'), 'calc': ('accent', 'accent-bg'),
    'warn': ('warn', 'warn-bg'), 'pivot': ('warn', 'warn-bg'), 'llm': ('warn', 'warn-bg'),
    'ok': ('ok', 'ok-bg'), 'outcome': ('ok', 'ok-bg'), 'pub': ('ok', 'ok-bg'),
    'gap': ('no', 'no-bg'), 'no': ('no', 'no-bg'),
}

ARROW_STYLE = {
    'text': ('text', '1.4', ''),
    'muted': ('muted', '1.2', ''),
    'up': ('ok', '1.8', ''),
    'down': ('accent', '1.8', ''),
    'warn': ('warn', '1.6', ''),
    'soft': ('muted', '1.3', ';stroke-dasharray:5 3'),
    'gap': ('no', '1.6', ';stroke-dasharray:6 4'),
}


class Flow:
    """정적 인라인 SVG 흐름도·구조도·회로도. 의미 축(lane)과 단방향 흐름을 지키고 화살표에 동작·조건을 적는다."""

    def __init__(self, w, h, label, mid, x0=0, y0=0):
        self.w, self.h, self.aria, self.mid = w, h, label, mid
        self.x0, self.y0 = x0, y0
        self.parts = []
        self._markers = {'text'}

    def add(self, s):
        self.parts.append(s)

    def text(self, x, y, t, size=12.5, weight=400, anchor='middle', color='text'):
        self.add(f'<text x="{x}" y="{y}" text-anchor="{anchor}" style="fill:{V(color)};font-size:{size}px;font-weight:{weight}">{esc(t)}</text>')

    def lane(self, x, y, w, title, sub=None):
        """구역·단계 머리말. 단순 번호가 아니라 이 단계의 역할·기준을 적는다."""
        self.text(x, y, title, size=12.5, weight=700, anchor='start', color='text')
        ly = y + 6
        if sub:
            self.text(x, y + 15, sub, size=11, weight=400, anchor='start', color='muted')
            ly = y + 21
        self.add(f'<line x1="{x}" y1="{ly}" x2="{x + w}" y2="{ly}" style="stroke:{V("text")};stroke-width:2"/>')

    def box(self, x, y, w, h, lines, kind='item', sub=None):
        """가운데 정렬 기본 상자. lines[0]은 굵게, 나머지는 보조 설명."""
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" style="{BOX[kind]}"/>')
        rows = ([('sub', sub)] if sub else []) + [('main' if i == 0 else 'rest', t) for i, t in enumerate(lines)]
        lh = 16
        top = y + h / 2 - (len(rows) - 1) * lh / 2 + 4
        cx = x + w / 2
        for i, (role, t) in enumerate(rows):
            if role == 'sub':
                self.text(cx, top + i * lh, t, size=11, color='muted')
            elif role == 'main':
                self.text(cx, top + i * lh, t, size=12.5, weight=600, color='no' if kind == 'gap' else 'text')
            else:
                self.text(cx, top + i * lh, t, size=11.5, color='no' if kind == 'gap' else 'muted')

    def card(self, x, y, w, h, title, lines=(), tone='accent', sub=None, badge=None, dashed=False):
        """차분한 패널 바탕에 왼쪽 4px 색 막대(점선이면 가설·한계·미구현)만 두어 시각 소음을 줄인 카드."""
        fg, bg = TONE_MAP.get(tone, ('accent', 'accent-bg'))
        is_dash = dashed or tone in ('gap', 'no')
        dash = ';stroke-dasharray:6 4' if is_dash else ''
        border_col = 'no' if tone in ('gap', 'no') else 'line'
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" style="fill:{V("panel")};stroke:{V(border_col)};stroke-width:1.3{dash}"/>')
        if not is_dash:
            self.add(f'<rect x="{x}" y="{y + 4}" width="4" height="{max(8, h - 8)}" rx="2" style="fill:{V(fg)};stroke:none"/>')
        tx = x + 12
        ty = y + 18
        bw = 0.0
        if badge:
            bw = text_width(badge, 10.5) + 12
            bx = x + w - bw - 8
            self.add(f'<rect x="{bx:.1f}" y="{y + 7}" width="{bw:.1f}" height="16" rx="8" style="fill:{V(bg)};stroke:none"/>')
            self.text(bx + bw / 2, y + 18.5, badge, size=10.5, weight=600, anchor='middle', color=fg)
        if sub:
            self.text(tx, ty, sub, size=10.5, weight=400, anchor='start', color='muted')
            ty += 15
        elif bw and text_width(title, 13) > (w - 22 - bw):
            ty += 14
        else:
            ty += 2
        self.text(tx, ty, title, size=13, weight=700, anchor='start', color='no' if tone in ('gap', 'no') else 'text')
        for i, line in enumerate(lines):
            self.text(tx, ty + 16 * (i + 1), line, size=11.5, weight=400, anchor='start', color='muted')

    def note(self, x, y, w, h, lines, tone='ok'):
        """그림 안쪽에 핵심 시사점·주의점을 짧게 짚는 보조 메모 상자."""
        fg, bg = TONE_MAP.get(tone, ('ok', 'ok-bg'))
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" style="fill:{V(bg)};stroke:none"/>')
        self.add(f'<rect x="{x}" y="{y}" width="3.5" height="{h}" rx="1.5" style="fill:{V(fg)};stroke:none"/>')
        rows = [lines] if isinstance(lines, str) else list(lines)
        lh = 15
        top = y + h / 2 - (len(rows) - 1) * lh / 2 + 4
        for i, line in enumerate(rows):
            self.text(x + 11, top + i * lh, line, size=11.5, weight=600 if i == 0 else 400, anchor='start', color=fg if i == 0 else 'text')

    def label(self, x, y, t, anchor='middle', size=11, color='muted', weight=400):
        self.text(x, y, t, size=size, anchor=anchor, color=color, weight=weight)

    def arrow(self, pts, label=None, lx=None, ly=None, gap=False, anchor='middle', both=False, kind=None, bg=True):
        ak = 'gap' if gap else (kind or 'text')
        col, sw, extra = ARROW_STYLE.get(ak, ARROW_STYLE['text'])
        self._markers.add(col)
        d = ' '.join(f'{x},{y}' for x, y in pts)
        st = f'fill:none;stroke:{V(col)};stroke-width:{sw};stroke-linejoin:round{extra}'
        mk = 'a' if col == 'text' else ('g' if col == 'no' else col[:2])
        start = f' marker-start="url(#{self.mid}{mk})"' if both else ''
        self.add(f'<polyline points="{d}" style="{st}" marker-end="url(#{self.mid}{mk})"{start}/>')
        if label:
            if bg and lx is not None and ly is not None:
                tw = text_width(label, 11) + 8
                rx = lx - tw / 2 if anchor == 'middle' else (lx - tw + 4 if anchor == 'end' else lx - 4)
                self.add(f'<rect x="{rx:.1f}" y="{ly - 11}" width="{tw:.1f}" height="14" rx="3" style="fill:{V("panel")};opacity:.9;stroke:none"/>')
            tcol = 'no' if ak == 'gap' else (col if ak in ('ok', 'accent', 'warn') else 'muted')
            self.text(lx, ly, label, size=11, anchor=anchor, color=tcol)

    def legend(self, x, y, items):
        """items: [(kind, '설명')] — 같은 모양이 그림에서 여러 번 나올 때만 넣는다."""
        cx = x
        for kind, t in items:
            self.add(f'<rect x="{cx}" y="{y - 11}" width="22" height="14" rx="3" style="{BOX[kind]}"/>')
            self.text(cx + 28, y, t, size=11.5, anchor='start', color='muted')
            cx += 28 + text_width(t, 11.5) + 22

    def render(self):
        m = self.mid
        mk_defs = []
        for col in sorted(self._markers):
            sfx = 'a' if col == 'text' else ('g' if col == 'no' else col[:2])
            mk_defs.append(
                f'<marker id="{m}{sfx}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" style="fill:{V(col)}"/></marker>'
            )
        defs = '<defs>' + ''.join(mk_defs) + '</defs>'
        return (f'<svg viewBox="{self.x0} {self.y0} {self.w} {self.h}" role="img" aria-label="{esc(self.aria)}" '
                f'style="color:{V("text")};font-family:inherit;max-width:{self.w}px;min-width:{min(self.w, 720)}px" xmlns="http://www.w3.org/2000/svg">' + defs + ''.join(self.parts) + '</svg>')


# ---------------------------------------------------------------- 대립·전환 대조도 (통념 -> 전환 계기 -> 재정의, AS-IS -> TO-BE)
def compare(pairs, label, mid, left_head=('기존 통념 · 문제 양상', '해체·개선 대상'),
            right_head=('전환된 원리 · 도달점', '재정의·해법'), via_head='전환 메커니즘', w=1000, row_h=58):
    """pairs: [('왼쪽 제목', '왼쪽 설명', '오른쪽 제목', '오른쪽 설명', '가운데 전환 동사/계기'), ...]"""
    top = 52
    gap_y = 10
    col_w = int((w - 20 - 168) / 2)
    lx = 10
    mx = lx + col_w
    rx = mx + 168
    H = top + len(pairs) * (row_h + gap_y) + 6
    f = Flow(w, H, label, mid)
    f.lane(lx, 18, col_w, left_head[0], left_head[1] or None)
    f.text(mx + 84, 24, via_head, size=11.5, weight=600, anchor='middle', color='muted')
    f.lane(rx, 18, col_w, right_head[0], right_head[1] or None)

    for i, (lt, ld, rt, rd, via) in enumerate(pairs):
        y = top + i * (row_h + gap_y)
        cy = y + row_h / 2
        f.card(lx, y, col_w, row_h, lt, [ld] if ld else (), tone='neutral', dashed=True)
        f.arrow([(lx + col_w + 6, cy), (rx - 8, cy)], via, mx + 84, cy - 8, kind='down', bg=True)
        f.card(rx, y, col_w, row_h, rt, [rd] if rd else (), tone='ok')
    return f.render()


# ---------------------------------------------------------------- 매핑·상관 격자 (가로 × 세로 다대다 교차)
CELL = {
    # 범용 상관·역할 부호
    'strong': (f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:1.6', 'text', 600),
    'rel': (f'fill:{V("panel")};stroke:{V("muted")};stroke-width:1.2', 'muted', 400),
    'pos': (f'fill:{V("ok-bg")};stroke:{V("ok")};stroke-width:1.4', 'ok', 600),
    'warn': (f'fill:{V("warn-bg")};stroke:{V("warn")};stroke-width:1.4', 'warn', 600),
    'gap': (f'fill:{V("no-bg")};stroke:{V("no")};stroke-width:1.3;stroke-dasharray:5 3', 'no', 400),
    'empty': (f'fill:none;stroke:{V("muted")};stroke-width:1;stroke-dasharray:3 3', 'muted', 400),
    # 기존 기술 문서 별칭 (하위 호환)
    'w': (f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:1.5', 'text', 600),
    'rw': (f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:2.5', 'text', 600),
    'r': (f'fill:{V("panel")};stroke:{V("muted")};stroke-width:1.2', 'muted', 400),
    'c': (f'fill:none;stroke:{V("muted")};stroke-width:1;stroke-dasharray:3 3', 'muted', 400),
    'h': (f'fill:{V("warn-bg")};stroke:{V("warn")};stroke-width:1.3', 'warn', 600),
    'ok': (f'fill:{V("ok-bg")};stroke:{V("ok")};stroke-width:1.3', 'ok', 600),
    'f': (f'fill:{V("no-bg")};stroke:{V("no")};stroke-width:1.3;stroke-dasharray:5 3', 'no', 400),
}


def matrix(cols, groups, label, mid, name_w=190, group_w=104, col_w=110, row_h=38, legend=None, top=58):
    """다대다 관계(개념 × 개념, 단계 × 대상, 주체 × 역할 등)를 선 엉킴 없이 격자로 보여 준다.
    cols:   [('열 이름', '작은 설명' 또는 '')]
    groups: [('묶음 이름\\n둘째 줄', [('행 이름', '작은 설명', 강조막대여부, {열번호: (칸종류, '칸 글자')})])]
    칸종류: strong 핵심/강함 · rel 연관/보조 · pos 해법/달성 · warn 주의/긴장 · gap 단절/미구현 (또는 w·rw·r·h·ok·f·c)"""
    x0 = group_w + name_w
    W = x0 + col_w * len(cols) + 10
    n_rows = sum(len(r) for _, r in groups)
    H = top + 30 + n_rows * row_h + (len(groups) - 1) * 10 + 14
    s = Flow(W, H, label, mid)
    if legend:
        lx = 10
        for kind, t in legend:
            st = CELL[kind][0]
            s.add(f'<rect x="{lx}" y="11" width="26" height="15" rx="4" style="{st}"/>')
            s.text(lx + 32, 23, t, size=11.5, anchor='start', color='muted')
            lx += 32 + text_width(t, 11.5) + 24
    hy = top + 14
    for i, (c, sub) in enumerate(cols):
        cx = x0 + col_w * i + col_w / 2
        s.text(cx, hy - 4, c, size=12.5, weight=600)
        if sub:
            s.text(cx, hy + 11, sub, size=10.5, color='muted')
    y = top + 30
    for g, rows in groups:
        gh = len(rows) * row_h
        s.add(f'<rect x="6" y="{y + 2}" width="{group_w - 12}" height="{gh - 4}" rx="6" style="fill:{V("accent-bg")};stroke:none"/>')
        gl = g.split('\n')
        for k, t in enumerate(gl):
            s.text(group_w / 2, y + gh / 2 + 4 + (k - (len(gl) - 1) / 2) * 14, t, size=11.5, weight=600 if k == 0 else 400, color='text' if k == 0 else 'muted')
        for ri, (name, note, pii, cells) in enumerate(rows):
            ry = y + ri * row_h
            if ri > 0:
                s.add(f'<line x1="{group_w}" y1="{ry}" x2="{W - 6}" y2="{ry}" style="stroke:{V("line")};stroke-width:1"/>')
            if pii:
                s.add(f'<rect x="{group_w}" y="{ry + 6}" width="4" height="{row_h - 12}" rx="2" style="fill:{V("warn")}"/>')
            s.text(group_w + 12, ry + row_h / 2 - (2 if note else -4), name, size=12, weight=600, anchor='start')
            if note:
                s.text(group_w + 12, ry + row_h / 2 + 12, note, size=10.5, anchor='start', color='muted')
            for ci, (kind, t) in cells.items():
                st, tc, fw = CELL[kind]
                cx = x0 + col_w * ci
                s.add(f'<rect x="{cx + 6}" y="{ry + 7}" width="{col_w - 12}" height="{row_h - 14}" rx="5" style="{st}"/>')
                s.add(f'<text x="{cx + col_w / 2}" y="{ry + row_h / 2 + 4}" text-anchor="middle" '
                      f'style="fill:{V(tc)};font-size:{10.5 if text_width(t, 11.5) > col_w - 20 else 11.5}px;font-weight:{fw}">{esc(t)}</text>')
        y += gh + 10
    for i in range(len(cols) + 1):
        x = x0 + col_w * i
        s.add(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{y - 10}" style="stroke:{V("line")};stroke-width:1;stroke-dasharray:2 4"/>')
    return s.render()


def figure(svg, caption, fid, dark=False):
    """caption: 그림에서 읽어야 할 핵심 요지 한두 문장(HTML 가능). fid: 문서 안에서 하나뿐인 id."""
    th = ' data-theme="dark"' if dark else ''
    return f'<figure class="fig" id="{fid}"{th}>{svg}<figcaption>{caption}</figcaption></figure>\n'


# ---------------------------------------------------------------- 초점 탐색형 다층 관계망 (도메인 중립: 개념망·모듈망·파이프라인)
NET_CSS = NET_MARK + r"""
[hidden]{display:none!important}
figure.fig-net{padding:14px 16px}
.dfn-bar{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-bottom:8px;font-size:12px;color:var(--fg-muted)}
.dfn-filters{display:inline-flex;flex-wrap:wrap;gap:4px}
.dfn-filters button{font:inherit;font-size:11.5px;padding:3px 10px;border:1px solid var(--fg-line);border-radius:999px;background:var(--fg-panel);color:var(--fg-muted);cursor:pointer}
.dfn-filters button.on{background:var(--fg-text);color:var(--fg-panel);border-color:var(--fg-text);font-weight:600}
.dfn-leg{display:inline-flex;flex-wrap:wrap;gap:6px 12px;margin-left:auto}
.dfn-leg span{display:inline-flex;align-items:center;gap:5px}
.dfn-ln{display:inline-block;width:18px;height:0;border-top:2.2px solid var(--fg-muted)}
.dfn-ln.up{border-color:var(--fg-ok)}.dfn-ln.dn{border-color:var(--fg-accent)}
.dfn-scroll{position:relative;overflow-x:auto;border:1px solid var(--fg-line);border-radius:8px;background:var(--fg-fill)}
.dfn-spacer{position:relative}
.dfn-canvas{position:absolute;left:12px;top:12px;transform-origin:0 0}
.dfn-wires{position:absolute;left:0;top:0;overflow:visible;pointer-events:none}
.dfn-wires path.w{fill:none;stroke:var(--fg-muted);stroke-width:1.15;opacity:.36;stroke-linejoin:round}
.dfn-wires path.a{fill:var(--fg-muted);stroke:none;opacity:.36}
.dfn-wires g.soft path.w{stroke-dasharray:4 3}
.dfn-wires g.on path.w{stroke:var(--fg-text);stroke-width:1.9;opacity:.95}
.dfn-wires g.on path.a{fill:var(--fg-text);opacity:.95}
.dfn-wires g.up path.w{stroke:var(--fg-ok);stroke-width:2.2;opacity:1}
.dfn-wires g.up path.a{fill:var(--fg-ok);opacity:1}
.dfn-wires g.dn path.w{stroke:var(--fg-accent);stroke-width:2.2;opacity:1}
.dfn-wires g.dn path.a{fill:var(--fg-accent);opacity:1}
.dfn-wires g.dim{opacity:.08}
.dfn-wires text.el{font-size:10px;fill:var(--fg-muted);opacity:0;transition:opacity .12s}
.dfn-wires g.up text.el,.dfn-wires g.dn text.el,.dfn-wires g.on text.el{opacity:1;font-weight:600}
.dfn-head{position:absolute;top:0;font-size:12.5px;font-weight:700;border-bottom:2px solid var(--fg-text);padding-bottom:3px;line-height:1.35;color:var(--fg-text)}
.dfn-head small{display:block;font-weight:400;color:var(--fg-muted);font-size:11px}
.dfn-node{position:absolute;background:var(--fg-panel);border:1px solid var(--fg-line);border-left:4px solid var(--fg-muted);border-radius:7px;padding:7px 9px;z-index:1;cursor:pointer;transition:opacity .12s;color:var(--fg-text)}
.dfn-node.T-accent{border-left-color:var(--fg-accent)}
.dfn-node.T-warn{border-left-color:var(--fg-warn)}
.dfn-node.T-ok{border-left-color:var(--fg-ok)}
.dfn-node.T-gap{border-left-color:var(--fg-no);border-style:dashed;border-left-width:3px}
.dfn-node.dashed{border-style:dashed}
.dfn-node.dim{opacity:.18}
.dfn-node.sel{outline:2px solid var(--fg-text);outline-offset:1px}
.dfn-node:focus-visible{outline:2px solid var(--fg-accent);outline-offset:1px}
.dfn-top{display:flex;justify-content:space-between;align-items:baseline;gap:6px}
.dfn-ttl{font-weight:700;font-size:12.5px;line-height:1.35}
.dfn-bdg{flex:none;font-size:10px;font-weight:600;border-radius:999px;padding:0 6px;background:var(--fg-fill);color:var(--fg-muted)}
.dfn-node.T-accent .dfn-bdg{background:var(--fg-accent-bg);color:var(--fg-accent)}
.dfn-node.T-warn .dfn-bdg{background:var(--fg-warn-bg);color:var(--fg-warn)}
.dfn-node.T-ok .dfn-bdg{background:var(--fg-ok-bg);color:var(--fg-ok)}
.dfn-sub{font-size:11px;color:var(--fg-muted);margin-top:2px;line-height:1.4}
.dfn-detail{margin-top:8px;padding:10px 13px;border:1px solid var(--fg-line);border-left:3px solid var(--fg-accent);border-radius:8px;background:var(--fg-fill);font-size:13px;line-height:1.55}
.dfn-detail .dh{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin-bottom:4px}
.dfn-detail .dh b{font-size:13.5px}
.dfn-detail .dh button{font:inherit;font-size:11.5px;border:0;background:transparent;color:var(--fg-muted);cursor:pointer}
.dfn-detail .dh button:hover{color:var(--fg-text)}
.dfn-links{margin-top:6px;display:flex;flex-wrap:wrap;gap:5px 8px;font-size:12px}
.dfn-chip{font:inherit;font-size:11.5px;padding:1px 8px;border:1px solid var(--fg-line);border-left-width:3px;border-radius:5px;background:var(--fg-panel);color:var(--fg-text);cursor:pointer}
.dfn-chip.up{border-left-color:var(--fg-ok)}.dfn-chip.dn{border-left-color:var(--fg-accent)}
.dfn-chip:hover{background:var(--fg-accent-bg)}
"""

NET_JS = f"""<script id="{NET_SCRIPT_ID}">
(function () {{
  const NS = 'http://www.w3.org/2000/svg';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
  const reach = (start, adj) => {{
    const seen = new Set(), st = [...start];
    while (st.length) {{ const x = st.pop(); (adj[x] || []).forEach(y => {{ if (!seen.has(y)) {{ seen.add(y); st.push(y); }} }}); }}
    return seen;
  }};

  function initNet(fig) {{
    if (fig.dataset.dfnReady) return;
    fig.dataset.dfnReady = '1';
    const dataEl = fig.querySelector('.dfn-data');
    if (!dataEl) return;
    const G = JSON.parse(dataEl.textContent);
    const W = G.nodeWidth || 216, GAPX = G.gapX || 72, GAPY = G.gapY || 10, TOP = 46, PAD = 12;
    const cv = fig.querySelector('.dfn-canvas'), svg = fig.querySelector('.dfn-wires'),
      scroller = fig.querySelector('.dfn-scroll'), spacer = fig.querySelector('.dfn-spacer'),
      detailBox = fig.querySelector('.dfn-detail'), filterBar = fig.querySelector('.dfn-filters');

    const N = {{}}; G.nodes.forEach(n => N[n.id] = n);
    const out = {{}}, inn = {{}}, edgeNote = {{}};
    G.edges.forEach(e => {{
      const [a, b, lbl] = e;
      (out[a] = out[a] || []).push(b);
      (inn[b] = inn[b] || []).push(a);
      if (lbl) edgeNote[a + '->' + b] = lbl;
    }});

    const EL = {{}}, HEAD = [];
    const state = {{ hover: null, pin: null, group: null }};

    G.stages.forEach((st, i) => {{
      const h = document.createElement('div'); h.className = 'dfn-head'; h.style.width = W + 'px';
      h.innerHTML = esc(st.title) + (st.sub ? '<small>' + esc(st.sub) + '</small>' : '');
      cv.appendChild(h); HEAD[i] = h;
    }});

    G.nodes.forEach(n => {{
      const d = document.createElement('div');
      d.className = 'dfn-node T-' + n.tone + (n.dashed ? ' dashed' : '');
      d.dataset.id = n.id; d.tabIndex = 0; d.setAttribute('role', 'button'); d.style.width = W + 'px';
      d.innerHTML = '<div class="dfn-top"><span class="dfn-ttl">' + esc(n.title) + '</span>'
        + (n.badge ? '<span class="dfn-bdg">' + esc(n.badge) + '</span>' : '') + '</div>'
        + (n.summary ? '<div class="dfn-sub">' + esc(n.summary) + '</div>' : '');
      cv.appendChild(d); EL[n.id] = d;
    }});

    const groups = [];
    G.nodes.forEach(n => {{ if (n.group && !groups.includes(n.group)) groups.push(n.group); }});
    if (groups.length && filterBar) {{
      const allBtn = document.createElement('button');
      allBtn.type = 'button'; allBtn.dataset.g = ''; allBtn.className = 'on'; allBtn.textContent = '전체';
      filterBar.appendChild(allBtn);
      groups.forEach(g => {{
        const b = document.createElement('button'); b.type = 'button'; b.dataset.g = g; b.textContent = g;
        filterBar.appendChild(b);
      }});
    }}

    function place() {{
      let maxH = 0;
      G.stages.forEach((st, i) => {{
        const x = i * (W + GAPX);
        HEAD[i].style.left = x + 'px';
        const want = {{}};
        if (i > 0) {{
          st.ids.forEach(id => {{
            const ys = (inn[id] || []).filter(a => N[a] && N[a].stage < i).map(a => EL[a].offsetTop + (EL[a].offsetHeight || 52) / 2);
            want[id] = ys.length ? ys.reduce((p, c) => p + c, 0) / ys.length - 26 : Infinity;
          }});
        }}
        let y = TOP;
        st.ids.forEach(id => {{
          const b = EL[id];
          if (i > 0 && want[id] !== Infinity) y = Math.max(y, Math.round(want[id]));
          b.style.left = x + 'px'; b.style.top = y + 'px';
          y += (b.offsetHeight || 54) + GAPY;
        }});
        maxH = Math.max(maxH, y);
      }});
      const totalW = Math.max(320, G.stages.length * (W + GAPX) - GAPX + 24);
      cv.style.width = totalW + 'px'; cv.style.height = maxH + 'px';
      svg.setAttribute('width', totalW); svg.setAttribute('height', maxH);
      const avail = scroller.clientWidth || totalW;
      const k = avail > 0 ? Math.min(1, avail / (totalW + PAD * 2)) : 1;
      cv.style.transform = k < 1 ? 'scale(' + k + ')' : '';
      spacer.style.width = Math.ceil((totalW + PAD * 2) * k) + 'px';
      spacer.style.height = Math.ceil((maxH + PAD * 2) * k) + 'px';
    }}

    const slot = {{}};
    G.stages.forEach(st => st.ids.forEach((id, idx) => slot[id] = idx));
    function edgePath(a, b) {{
      const ba = EL[a], bb = EL[b];
      const ay = ba.offsetTop + (ba.offsetHeight || 52) / 2, by = bb.offsetTop + (bb.offsetHeight || 52) / 2;
      const ar = ba.offsetLeft + W, bl = bb.offsetLeft, br = bb.offsetLeft + W;
      const s = slot[a] || 0;
      if (N[a].stage >= N[b].stage) {{
        const xm = Math.max(ar, br) + 14 + (s % 5) * 5;
        return {{ d: `M${{ar}},${{ay}} H${{xm}} V${{by}} H${{br + 6}}`, arw: `M${{br}},${{by}} l6,-3.2 v6.4 z`, lx: xm, ly: (ay + by) / 2 }};
      }}
      const xm = bl - 14 - (s % 7) * 6;
      return {{ d: `M${{ar}},${{ay}} H${{xm}} V${{by}} H${{bl - 6}}`, arw: `M${{bl}},${{by}} l-6,-3.2 v6.4 z`, lx: (ar + bl) / 2, ly: by - 5 }};
    }}

    function renderDetail(id) {{
      if (!id || !N[id]) {{ detailBox.hidden = true; return; }}
      const n = N[id], ups = inn[id] || [], dns = out[id] || [];
      const chip = (tid, dir) => {{
        const rel = dir === 'up' ? edgeNote[tid + '->' + id] : edgeNote[id + '->' + tid];
        return '<button type="button" class="dfn-chip ' + dir + '" data-go="' + esc(tid) + '">'
          + (dir === 'up' ? '← ' : '→ ') + esc(N[tid].title) + (rel ? ' (' + esc(rel) + ')' : '') + '</button>';
      }};
      let h = '<div class="dh"><b>' + esc(n.title) + '</b><button type="button" data-clear>선택 해제 ✕</button></div>';
      if (n.detail || n.summary) h += '<div>' + esc(n.detail || n.summary) + '</div>';
      if (ups.length || dns.length) {{
        h += '<div class="dfn-links">' + ups.map(u => chip(u, 'up')).join('') + dns.map(d => chip(d, 'dn')).join('') + '</div>';
      }}
      detailBox.innerHTML = h;
      detailBox.hidden = false;
    }}

    function refresh() {{
      place();
      let keep = null, edgeCls = null;
      if (state.pin && N[state.pin]) {{
        const id = state.pin, U = new Set([id, ...reach([id], inn)]), D = new Set([id, ...reach([id], out)]);
        keep = new Set([...U, ...D]);
        edgeCls = (a, b) => (U.has(a) && U.has(b)) ? 'up' : (D.has(a) && D.has(b)) ? 'dn' : 'dim';
      }} else if (state.hover && N[state.hover]) {{
        const id = state.hover;
        keep = new Set([id, ...(inn[id] || []), ...(out[id] || [])]);
        edgeCls = (a, b) => (a === id || b === id) ? 'on' : 'dim';
      }} else if (state.group) {{
        const seed = G.nodes.filter(n => n.group === state.group).map(n => n.id);
        const U = reach(seed, inn), D = reach(seed, out);
        keep = new Set([...seed, ...U, ...D]);
        edgeCls = (a, b) => (keep.has(a) && keep.has(b)) ? 'dn' : 'dim';
      }}
      svg.innerHTML = '';
      G.edges.forEach(e => {{
        const [a, b, lbl, soft] = e;
        if (!EL[a] || !EL[b]) return;
        const p = edgePath(a, b);
        const g = document.createElementNS(NS, 'g');
        const cls = ((edgeCls ? edgeCls(a, b) : '') + (soft ? ' soft' : '')).trim();
        if (cls) g.setAttribute('class', cls);
        g.innerHTML = `<path class="w" d="${{p.d}}"/><path class="a" d="${{p.arw}}"/>`
          + (lbl ? `<text class="el" x="${{p.lx}}" y="${{p.ly}}" text-anchor="middle">${{esc(lbl)}}</text>` : '');
        svg.appendChild(g);
      }});
      Object.values(EL).forEach(el => {{
        el.classList.toggle('dim', !!keep && !keep.has(el.dataset.id));
        el.classList.toggle('sel', state.pin === el.dataset.id);
      }});
      if (filterBar) {{
        filterBar.querySelectorAll('button').forEach(b => b.classList.toggle('on', (b.dataset.g || null) === state.group));
      }}
      renderDetail(state.pin);
    }}

    cv.addEventListener('mouseover', e => {{
      if (state.pin) return;
      const nd = e.target.closest('.dfn-node'), id = nd ? nd.dataset.id : null;
      if (id !== state.hover) {{ state.hover = id; refresh(); }}
    }});
    cv.addEventListener('mouseleave', () => {{ if (state.hover) {{ state.hover = null; refresh(); }} }});
    cv.addEventListener('click', e => {{
      const nd = e.target.closest('.dfn-node');
      if (nd) {{ state.pin = state.pin === nd.dataset.id ? null : nd.dataset.id; state.hover = null; refresh(); }}
      else if (state.pin) {{ state.pin = null; refresh(); }}
    }});
    cv.addEventListener('keydown', e => {{
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const nd = e.target.closest('.dfn-node');
      if (nd) {{ e.preventDefault(); state.pin = state.pin === nd.dataset.id ? null : nd.dataset.id; refresh(); }}
    }});
    detailBox.addEventListener('click', e => {{
      if (e.target.closest('[data-clear]')) {{ state.pin = null; refresh(); return; }}
      const go = e.target.closest('[data-go]');
      if (go && N[go.dataset.go]) {{ state.pin = go.dataset.go; refresh(); }}
    }});
    if (filterBar) {{
      filterBar.addEventListener('click', e => {{
        const b = e.target.closest('button'); if (!b) return;
        state.group = b.dataset.g || null; state.pin = null; refresh();
      }});
    }}
    document.addEventListener('keydown', e => {{ if (e.key === 'Escape' && state.pin) {{ state.pin = null; refresh(); }} }});
    if (typeof ResizeObserver !== 'undefined') {{
      let lw = 0;
      new ResizeObserver(() => {{ const w = scroller.clientWidth; if (w > 0 && w !== lw) {{ lw = w; refresh(); }} }}).observe(scroller);
    }} else {{ window.addEventListener('resize', refresh); }}
    refresh();
  }}

  function boot() {{ document.querySelectorAll('figure.fig-net').forEach(initNet); }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}})();
</script>
"""


def _normalize_network(data):
    raw_stages = data.get('stages') or data.get('lanes') or []
    assert len(raw_stages) >= 2, 'network: 최소 2개 이상의 의미 단계(stages)가 필요합니다'
    stages = []
    for st in raw_stages:
        if isinstance(st, (tuple, list)):
            stages.append({'title': str(st[0]), 'sub': str(st[1]) if len(st) > 1 else '', 'ids': []})
        elif isinstance(st, dict):
            stages.append({'title': str(st['title']), 'sub': str(st.get('sub', '')), 'ids': []})
        else:
            stages.append({'title': str(st), 'sub': '', 'ids': []})

    tone_norm = {
        'neutral': 'neutral', 'muted': 'neutral', 'source': 'neutral',
        'accent': 'accent', 'step': 'accent', 'calc': 'accent',
        'warn': 'warn', 'pivot': 'warn', 'llm': 'warn',
        'ok': 'ok', 'outcome': 'ok', 'pub': 'ok',
        'gap': 'gap', 'no': 'gap',
    }
    nodes = []
    seen = set()
    for raw in (data.get('nodes') or []):
        nid = str(raw['id'])
        assert nid not in seen, f'network: 중복 노드 id: {nid}'
        seen.add(nid)
        si = int(raw.get('stage', raw.get('lane', 0)))
        assert 0 <= si < len(stages), f'network: {nid}의 stage={si}가 범위 밖입니다'
        stages[si]['ids'].append(nid)
        t = tone_norm.get(str(raw.get('tone', 'accent')), 'accent')
        nodes.append({
            'id': nid,
            'title': str(raw.get('title', raw.get('name', nid))),
            'stage': si,
            'tone': t,
            'badge': str(raw.get('badge', '')),
            'summary': str(raw.get('summary', '')),
            'detail': str(raw.get('detail', '')),
            'group': str(raw.get('group', '')),
            'dashed': bool(raw.get('dashed', t == 'gap')),
        })

    edges = []
    for e in (data.get('edges') or []):
        a, b = str(e[0]), str(e[1])
        assert a in seen and b in seen, f'network: 존재하지 않는 노드를 잇는 간선: {a!r} -> {b!r}'
        lbl = str(e[2]) if len(e) > 2 and e[2] else ''
        soft = bool(e[3]) if len(e) > 3 else False
        edges.append([a, b, lbl, soft])

    out = {'stages': stages, 'nodes': nodes, 'edges': edges}
    for k in ('nodeWidth', 'gapX', 'gapY', 'allowBack'):
        if k in data:
            out[k] = data[k]
    return out


def network(data, caption, fid='fig-net', label=None, up_label='선행 · 원인', down_label='후행 · 파급', dark=False):
    """노드가 많아 정적 선만으로는 엉키는 다층 관계를 초점 탐색형으로 보여 준다 (특정 도메인 종속 없음).
    - 평상시엔 연한 골격선만 노출해 본문 흐름을 해치지 않고, 노드를 고르면 선행 요인(초록)·후행 파급(파랑)만 끝까지 밝힌다."""
    norm = _normalize_network(data)
    aria = label or f'{norm["stages"][0]["title"]}부터 {norm["stages"][-1]["title"]}까지 노드 {len(norm["nodes"])}개·연결 {len(norm["edges"])}개의 관계망'
    th = ' data-theme="dark"' if dark else ''
    jstr = json.dumps(norm, ensure_ascii=False).replace('</', '<\\/')
    return (
        f'<figure class="fig fig-net" id="{esc(fid)}"{th}>\n'
        f'<div class="dfn-bar"><div class="dfn-filters"></div>'
        f'<div class="dfn-leg"><span><i class="dfn-ln up"></i>{esc(up_label)}</span><span><i class="dfn-ln dn"></i>{esc(down_label)}</span></div></div>\n'
        f'<div class="dfn-scroll"><div class="dfn-spacer"><div class="dfn-canvas"><svg class="dfn-wires" role="img" aria-label="{esc(aria)}"></svg></div></div></div>\n'
        f'<div class="dfn-detail" aria-live="polite" hidden></div>\n'
        f'<figcaption>{caption}</figcaption>\n'
        f'<script type="application/json" class="dfn-data">{jstr}</script>\n'
        f'</figure>\n'
    )


# ---------------------------------------------------------------- 문서 고치기 (삽입·치환·선택적 판 관리)
class Doc:
    def __init__(self, path):
        self.path = path
        raw = io.open(path, encoding='utf-8', newline='').read()
        self.crlf = '\r\n' in raw
        self.html = raw.replace('\r\n', '\n')
        self._css()

    def _css(self):
        if MARK in self.html:
            return
        if '</style>' in self.html:
            i = self.html.index('</style>')
            self.html = self.html[:i] + FIG_CSS + self.html[i:]
        elif '</head>' in self.html:
            i = self.html.index('</head>')
            self.html = self.html[:i] + '<style>\n' + FIG_CSS + '</style>\n' + self.html[i:]
        else:
            self.html = '<style>\n' + FIG_CSS + '</style>\n' + self.html

    def _ensure_net_assets(self):
        if 'fig-net' not in self.html:
            return
        if NET_MARK not in self.html:
            i = self.html.index('</style>')
            self.html = self.html[:i] + NET_CSS + self.html[i:]
        if f'id="{NET_SCRIPT_ID}"' not in self.html:
            if '</body>' in self.html:
                i = self.html.rindex('</body>')
                self.html = self.html[:i] + NET_JS + self.html[i:]
            else:
                self.html += '\n' + NET_JS

    def _one(self, old):
        c = self.html.count(old)
        assert c == 1, f'{os.path.basename(self.path)}: 기준 문자열이 {c}번 나옴: {old[:80]!r}'

    def insert_after(self, anchor, html):
        self._one(anchor)
        self.html = self.html.replace(anchor, anchor + html)

    def insert_before(self, anchor, html):
        self._one(anchor)
        self.html = self.html.replace(anchor, html + anchor)

    def replace(self, old, new):
        self._one(old)
        self.html = self.html.replace(old, new)

    def replace_re(self, pattern, new):
        ms = list(re.finditer(pattern, self.html, re.S))
        assert len(ms) == 1, f'{os.path.basename(self.path)}: 패턴이 {len(ms)}번: {pattern[:60]}'
        m = ms[0]
        self.html = self.html[:m.start()] + new + self.html[m.end():]

    def version(self):
        m = re.search(r'버전 (?:<b>)?(v?)(\d+)\.(\d+)(?:</b>)?', self.html)
        assert m, '문서 맨 위 버전 표기를 찾지 못함'
        return m

    def bump(self, history_text, date):
        """문서가 '버전 x.y'와 '변경 이력' 표를 쓰는 경우: 이전 판을 archive/<이름>_v<판>.html로 두고 판을 0.1 올린다."""
        m = self.version()
        pre, major, minor = m.group(1), int(m.group(2)), int(m.group(3))
        old_v, new_v = f'{major}.{minor}', f'{major}.{minor + 1}'
        base = os.path.splitext(os.path.basename(self.path))[0]
        arch_dir = os.path.join(os.path.dirname(self.path) or '.', 'archive')
        os.makedirs(arch_dir, exist_ok=True)
        arch = os.path.join(arch_dir, f'{base}_v{old_v}.html')
        if not os.path.exists(arch):
            shutil.copyfile(self.path, arch)
        whole = m.group(0)
        self.html = self.html.replace(whole, whole.replace(f'{pre}{old_v}', f'{pre}{new_v}'), 1)
        k = self.html.find('변경 이력')
        assert k >= 0, '변경 이력 절이 없음'
        rm = re.compile(r'<tr><td>(v?)\d+\.\d+</td>').search(self.html, k)
        assert rm, '변경 이력 표의 행을 찾지 못함'
        rel = os.path.relpath(arch, os.path.dirname(self.path) or '.').replace(os.sep, '/')
        row = (f'<tr><td>{rm.group(1)}{new_v}</td><td>{date}</td><td>{history_text} '
               f'<a href="{rel}">{rm.group(1)}{old_v} 보관본</a></td></tr>\n')
        self.html = self.html[:rm.start()] + row + self.html[rm.start():]
        return new_v

    def save(self):
        self._ensure_net_assets()
        out = self.html.replace('\n', '\r\n') if self.crlf else self.html
        io.open(self.path, 'w', encoding='utf-8', newline='').write(out)


# ---------------------------------------------------------------- 점검·스크린샷
def _check_svg_geometry(svg_body, probs):
    vb_m = re.search(r'<svg[^>]*\bviewBox="([-\d.]+)\s+([-\d.]+)\s+([\d.]+)\s+([\d.]+)"', svg_body)
    if not vb_m:
        return
    x0, y0, vw, vh = [float(v) for v in vb_m.groups()]
    x_min, x_max, y_min, y_max = x0 - 4, x0 + vw + 4, y0, y0 + vh + 4
    for tm in re.finditer(r'<text\s+x="([-\d.]+)"\s+y="([-\d.]+)"(?:\s+text-anchor="([^"]+)")?\s+style="[^"]*font-size:([\d.]+)px[^"]*">(.*?)</text>', svg_body):
        tx, ty = float(tm.group(1)), float(tm.group(2))
        anc = tm.group(3) or 'start'
        sz = float(tm.group(4))
        raw_txt = unesc(tm.group(5))
        tw = text_width(raw_txt, sz)
        lx = tx - tw / 2 if anc == 'middle' else (tx - tw if anc == 'end' else tx)
        rx = tx + tw / 2 if anc == 'middle' else (tx if anc == 'end' else tx + tw)
        if lx < x_min or rx > x_max or ty - sz < y_min - 4 or ty > y_max:
            probs.append(f'SVG viewBox 밖 글자 잘림 우려: "{raw_txt[:24]}" (x={lx:.0f}..{rx:.0f}, viewBox폭={vw:.0f})')


def check(path):
    s = io.open(path, encoding='utf-8').read()
    probs = []
    dom = re.sub(r'<script\b.*?</script>', '', s, flags=re.S)
    for m in re.finditer(r'<svg\b.*?</svg>', dom, re.S):
        body = m.group(0)
        if re.search(r'<script|<foreignObject|<image|href="http', body):
            probs.append('svg 안에 script·foreignObject·image·외부 링크')
        if 'aria-label=' not in body[:400] and 'aria-hidden="true"' not in body[:400]:
            probs.append('svg에 aria-label 없음')
        _check_svg_geometry(body, probs)
    figs = re.findall(r'<figure class="fig(?:\s+[^"]*)?"[^>]*>.*?</figure>', dom, re.S)
    for f in figs:
        if '<figcaption>' not in f:
            probs.append('figcaption 없는 그림')
    ids = re.findall(r'<figure class="fig(?:\s+[^"]*)?"[^>]*\bid="([^"]+)"', dom)
    if len(ids) != len(set(ids)):
        probs.append('그림 id 중복')
    mids = re.findall(r'<marker id="([^"]+)"', dom)
    if len(mids) != len(set(mids)):
        probs.append('marker id 중복 (Flow의 mid를 그림마다 다르게)')

    for jm in re.finditer(r'<script type="application/json" class="dfn-data">(.*?)</script>', s, re.S):
        try:
            g = json.loads(jm.group(1))
        except Exception as e:
            probs.append(f'network JSON 파싱 오류: {e}')
            continue
        stages = g.get('stages') or []
        if len(stages) > 7:
            probs.append(f'network 단계 과다({len(stages)}개) — 의미 축 기준으로 3~6단계 이내로 묶으세요')
        nmap = {n['id']: n for n in (g.get('nodes') or [])}
        back = []
        for e in (g.get('edges') or []):
            a, b = e[0], e[1]
            if a not in nmap or b not in nmap:
                probs.append(f'network 없는 노드 참조: {a} -> {b}')
            elif nmap[a].get('stage', 0) > nmap[b].get('stage', 0) and not g.get('allowBack'):
                back.append(f'{a}->{b}')
        if back:
            probs.append(f'network 역방향(오른쪽→왼쪽) 간선 {len(back)}개({", ".join(back[:4])}) — 선행→후행 단방향으로 배치하세요')
    if 'fig-net' in dom and f'id="{NET_SCRIPT_ID}"' not in s:
        probs.append('network 스크립트 누락 (Doc.save()로 저장하세요)')

    base = os.path.dirname(path) or '.'
    for h in re.findall(r'href="([^"#]+)', dom):
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', h):
            continue
        if not os.path.exists(os.path.normpath(os.path.join(base, urllib.parse.unquote(h)))):
            probs.append(f'깨진 링크: {h}')
    anchors = set(re.findall(r'\bid="([^"]+)"', dom))
    for a in re.findall(r'href="#([^"?"]+)', dom):
        if a not in anchors:
            probs.append(f'없는 앵커: #{a}')
    if re.search(r'<(script|link)[^>]+(src|href)="https?://', s):
        probs.append('외부 스크립트·스타일')
    tag = '[통과]' if not probs else '[문제]'
    print(f'{tag} {path} · 그림 {len(figs)}개')
    for p in probs:
        print('   -', p)
    return not probs


def _chrome():
    candidates = [
        shutil.which('chrome'),
        shutil.which('google-chrome'),
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        shutil.which('msedge'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    raise SystemExit('Chrome/Edge를 찾지 못했습니다')


def _headless_profile_dir():
    """Headless Chrome이 매 실행마다 빈 암호 확인(Windows LogonUserW -> Event 4625/4740)을 하지 않도록
    os_password_last_changed 캐시가 포함된 고정 프로필 폴더를 준비한다."""
    tmp = os.environ.get('TEMP') or os.environ.get('TMPDIR') or '/tmp'
    prof = os.path.join(tmp, 'docfig-chrome-profile')
    os.makedirs(prof, exist_ok=True)
    local_state = os.path.join(prof, 'Local State')
    src_state = os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\User Data\Local State')
    try:
        pw_mgr = {'os_password_blank': False, 'os_password_last_changed': '13359901926290193'}
        if os.path.exists(src_state):
            with io.open(src_state, encoding='utf-8') as f:
                pw_mgr = json.load(f).get('password_manager', pw_mgr)
        state = {}
        if os.path.exists(local_state):
            with io.open(local_state, encoding='utf-8') as f:
                state = json.load(f)
        cur_pm = state.get('password_manager') if isinstance(state.get('password_manager'), dict) else {}
        if cur_pm.get('os_password_last_changed') != pw_mgr.get('os_password_last_changed'):
            cur_pm.update(pw_mgr)
            state['password_manager'] = cur_pm
            with io.open(local_state, 'w', encoding='utf-8') as f:
                json.dump(state, f)
    except Exception:
        pass
    return prof


def shot(path, out_dir):
    """그림마다 밝은·어두운 화면 PNG. 문서의 <style>(및 network 런타임)을 함께 넣어 실제 모양 그대로 찍는다."""
    s = io.open(path, encoding='utf-8').read()
    style = ''.join(re.findall(r'<style>.*?</style>', s, re.S))
    njs_m = re.search(rf'<script id="{NET_SCRIPT_ID}">.*?</script>', s, re.S)
    njs = njs_m.group(0) if njs_m else ''
    figs = re.findall(r'<figure class="fig(?:\s+[^"]*)?"[^>]*>.*?</figure>', s, re.S)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    chrome = _chrome()
    profile_dir = _headless_profile_dir()
    outs = []
    for i, f in enumerate(figs, 1):
        is_net = 'dfn-data' in f
        if is_net:
            w, h, extra_js, extra_flags = 1280, 960, njs, ['--virtual-time-budget=1000']
        else:
            vb = re.search(r'<svg viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', f)
            w = 1100
            h = int(float(vb.group(2))) + 260 if vb else 900
            extra_js, extra_flags = '', []
        for theme in ('light', 'dark'):
            attr = ' data-theme="dark"' if theme == 'dark' else ' data-theme="light"'
            bg = DARK['panel'] if theme == 'dark' else LIGHT['panel']
            page = (f'<!doctype html><html{attr}><head><meta charset="utf-8">{style}</head>'
                    f'<body style="margin:0;padding:16px;width:{w - 40}px;background:{bg}"><main>{f}</main>{extra_js}</body></html>')
            hp = os.path.join(out_dir, f'{base}_{i}_{theme}.html')
            io.open(hp, 'w', encoding='utf-8').write(page)
            png = os.path.abspath(os.path.join(out_dir, f'{base}_{i}_{theme}.png'))
            uri = pathlib.Path(hp).resolve().as_uri()
            subprocess.run([chrome, '--headless=new', '--disable-gpu', '--hide-scrollbars',
                            '--no-first-run', '--no-default-browser-check', '--password-store=basic',
                            *extra_flags,
                            f'--user-data-dir={profile_dir}',
                            f'--window-size={w},{h}', f'--screenshot={png}', uri],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            outs.append(png)
    for o in outs:
        print(o)
    return outs


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'check':
        ok = all([check(p) for p in sys.argv[2:]])
        sys.exit(0 if ok else 1)
    if len(sys.argv) >= 3 and sys.argv[1] == 'shot':
        default_tmp = os.path.join(os.environ.get('TEMP') or os.environ.get('TMPDIR') or '/tmp', 'docfig')
        shot(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else default_tmp)
        sys.exit(0)
    print(__doc__)
