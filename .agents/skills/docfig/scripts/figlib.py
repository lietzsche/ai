r"""docfig: 문서(HTML)에 직접 쓰는 인라인 SVG·연결도 그림 도구. 외부 라이브러리·이미지·웹폰트 없이 오프라인·폐쇄망에서도 열린다.

쓰는 법 (그림 만드는 임시 스크립트에서):
    import sys; sys.path.insert(0, '.agents/skills/docfig/scripts')  # 또는 현재 프로젝트의 figlib.py가 있는 경로
    from figlib import Flow, matrix, lineage, tab_wrap, figure, Doc

    # 1) 정적 흐름도·구조도 (상자 ~15개 안팎)
    f = Flow(1000, 300, '그림이 말하는 한 문장(스크린리더용)', 'dep')   # 'dep' = 문서 안에서 겹치지 않는 짧은 id
    f.lane(10, 28, 300, '1단계 · 점검', '배포 전 자동 확인')
    f.card(10, 60, 160, 64, '사전점검', ['스키마·권한 확인'], tone='calc', badge='코드')
    f.arrow([(170, 92), (228, 92)], '통과하면', 199, 84)
    svg = f.render()

    # 2) 다단 표·열 연결도(ERD·리니지, 표 10개 이상이거나 열 단위 계보 추적 시)
    fig_html = lineage(data_dict, '그림 설명과 읽는 법', fid='fig-erd')

    d = Doc('docs/deploy-guide.html')
    d.insert_after('<h2 id="s5">5. 배포</h2>\n', figure(svg, '그림 설명 한두 문장', 'fig-deploy'))
    d.save()

명령줄:
    python .agents/skills/docfig/scripts/figlib.py check <html>...       그림·연결도·링크 점검 (외부 의존성, aria-label, 역방향 간선, 깨진 링크)
    python .agents/skills/docfig/scripts/figlib.py shot <html> [폴더]     그림마다 밝은·어두운 화면 스크린샷(PNG). 글자 겹침·잘림을 눈으로 본다
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
LINEAGE_MARK = '/* docfig-lineage */'
LINEAGE_SCRIPT_ID = 'docfig-lineage-js'


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


def text_width(t, size=12.0):
    """한글·전각은 넓게, 영문·숫자는 좁게 어림한 글자 폭(px). 상자 폭·범례 간격 계산용."""
    return sum((0.95 if ord(ch) > 0x2000 else 0.56) * size for ch in str(t))


BOX = {
    'item': f'fill:{V("panel")};stroke:{V("line")};stroke-width:1.5',          # 표·파일·구성요소
    'pii': f'fill:{V("panel")};stroke:{V("warn")};stroke-width:2.5',           # 개인정보·민감정보 있음
    'step': f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:1.5',   # 단계·명령·처리
    'llm': f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:3',      # LLM·모델을 부르는 곳
    'person': f'fill:{V("warn-bg")};stroke:{V("warn")};stroke-width:1.5',     # 사람이 하는 일
    'ok': f'fill:{V("ok-bg")};stroke:{V("ok")};stroke-width:1.5',             # 완료·통과
    'gap': f'fill:{V("no-bg")};stroke:{V("no")};stroke-width:1.5;stroke-dasharray:6 4',  # 아직 없음·막힘
    'group': f'fill:none;stroke:{V("line")};stroke-width:1.5',                 # 묶음 테두리
    'band': f'fill:{V("fill")};stroke:{V("line")};stroke-width:1',             # 배경 띠
}

TONE_COLOR = {
    'source': ('muted', 'fill'), 'silver': ('muted', 'fill'), 'muted': ('muted', 'fill'),
    'calc': ('accent', 'accent-bg'), 'gold': ('accent', 'accent-bg'), 'accent': ('accent', 'accent-bg'),
    'llm': ('warn', 'warn-bg'), 'infer': ('warn', 'warn-bg'), 'warn': ('warn', 'warn-bg'),
    'pub': ('ok', 'ok-bg'), 'output': ('ok', 'ok-bg'), 'ok': ('ok', 'ok-bg'),
    'gap': ('no', 'no-bg'), 'no': ('no', 'no-bg'),
}

ARROW_STYLE = {
    'text': ('text', '1.4', ''),
    'muted': ('muted', '1.2', ''),
    'up': ('ok', '1.8', ''),
    'down': ('accent', '1.8', ''),
    'soft': ('muted', '1.3', ';stroke-dasharray:5 3'),
    'gap': ('no', '1.6', ';stroke-dasharray:6 4'),
}


class Flow:
    """흐름도·구조도. 좌표는 viewBox 기준(px). 의미 있는 레인과 단방향(왼→오) 정렬을 지키고 화살표에는 뜻을 적는다."""

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
        """레인의 역할과 실행 계기를 머리말로 표시한다."""
        self.text(x, y, title, size=12.5, weight=700, anchor='start', color='text')
        ly = y + 6
        if sub:
            self.text(x, y + 15, sub, size=11, weight=400, anchor='start', color='muted')
            ly = y + 21
        self.add(f'<line x1="{x}" y1="{ly}" x2="{x + w}" y2="{ly}" style="stroke:{V("text")};stroke-width:2"/>')

    def box(self, x, y, w, h, lines, kind='item', sub=None):
        """lines[0]은 굵게, 나머지는 작게. sub는 맨 위 회색 작은 글씨(층·위치 이름)."""
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

    def card(self, x, y, w, h, title, lines=(), tone='calc', sub=None, badge=None, dashed=False):
        """원색 채움 대신 왼쪽 4px 색 막대와 점선 테두리(계획·미구현)로 성격을 구분하는 정돈된 카드."""
        fg, bg = TONE_COLOR.get(tone, ('accent', 'accent-bg'))
        is_dash = dashed or tone in ('gap', 'no')
        dash = ';stroke-dasharray:6 4' if is_dash else ''
        border_col = 'no' if tone in ('gap', 'no') else 'line'
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" style="fill:{V("panel")};stroke:{V(border_col)};stroke-width:1.3{dash}"/>')
        if not is_dash:
            self.add(f'<rect x="{x}" y="{y + 4}" width="4" height="{max(8, h - 8)}" rx="2" style="fill:{V(fg)};stroke:none"/>')
        tx = x + 12
        ty = y + 18
        if badge:
            bw = text_width(badge, 10.5) + 12
            bx = x + w - bw - 8
            self.add(f'<rect x="{bx}" y="{y + 7}" width="{bw:.1f}" height="16" rx="8" style="fill:{V(bg)};stroke:none"/>')
            self.text(bx + bw / 2, y + 18.5, badge, size=10.5, weight=600, anchor='middle', color=fg)
        if sub:
            self.text(tx, ty, sub, size=10.5, weight=400, anchor='start', color='muted')
            ty += 15
        else:
            ty += 2
        self.text(tx, ty, title, size=13, weight=700, anchor='start', color='no' if tone in ('gap', 'no') else 'text')
        for i, line in enumerate(lines):
            self.text(tx, ty + 16 * (i + 1), line, size=11.5, weight=400, anchor='start', color='muted')

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
                self.add(f'<rect x="{rx:.1f}" y="{ly - 11}" width="{tw:.1f}" height="14" rx="3" style="fill:{V("panel")};opacity:.88;stroke:none"/>')
            tcol = 'no' if ak == 'gap' else (col if ak in ('up', 'down') else 'muted')
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


# ---------------------------------------------------------------- 매핑 그림 (가로 × 세로 격자)
CELL = {
    'w': (f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:1.5', 'text', 600),    # 씀
    'rw': (f'fill:{V("accent-bg")};stroke:{V("accent")};stroke-width:2.5', 'text', 600),   # 읽고 씀
    'r': (f'fill:{V("panel")};stroke:{V("muted")};stroke-width:1.2', 'muted', 400),        # 읽음
    'c': (f'fill:none;stroke:{V("muted")};stroke-width:1;stroke-dasharray:3 3', 'muted', 400),  # 자리만·빈 표
    'h': (f'fill:{V("warn-bg")};stroke:{V("warn")};stroke-width:1.3', 'warn', 600),        # 사람이 함
    'ok': (f'fill:{V("ok-bg")};stroke:{V("ok")};stroke-width:1.3', 'ok', 600),             # 완료·있음
    'f': (f'fill:{V("no-bg")};stroke:{V("no")};stroke-width:1.3;stroke-dasharray:5 3', 'no', 400),  # 아직 없음
}


def matrix(cols, groups, label, mid, name_w=190, group_w=104, col_w=100, row_h=38, legend=None, top=58):
    """다대다 관계(단계 × 표, 주체 × 저장소, 환경 × 설정 등)를 격자로.
    cols:   [('열 이름', '작은 설명' 또는 '')]
    groups: [('묶음 이름\\n둘째 줄', [('행 이름', '작은 설명', 개인정보여부, {열번호: (칸종류, '칸 글자')})])]
    칸종류: w 씀 · rw 읽고 씀 · r 읽음 · c 자리만 · h 사람이 함 · ok 완료 · f 아직 없음
    legend: [(칸종류, '설명')]"""
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
    """caption: 그림이 보여 주는 것과 읽는 법을 한두 문장(HTML 가능). fid: 문서 안에서 하나뿐인 id."""
    th = ' data-theme="dark"' if dark else ''
    return f'<figure class="fig" id="{fid}"{th}>{svg}<figcaption>{caption}</figcaption></figure>\n'


# ---------------------------------------------------------------- 대화형 다단 연결도·계보도 (ERD·데이터 리니지)
LINEAGE_CSS = LINEAGE_MARK + r"""
[hidden]{display:none!important}
figure.fig-lineage{padding:14px 16px;overflow:visible}
.df-lead{margin:0 0 6px;font-size:13.5px;color:var(--fg-muted);line-height:1.55;max-width:none}
.df-bar{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:6px 0 8px;font-size:12.5px}
.df-bar .df-lb{color:var(--fg-muted)}
.df-seg{display:inline-flex;border:1px solid var(--fg-line);border-radius:999px;overflow:hidden;background:var(--fg-panel)}
.df-seg button{font:inherit;font-size:12px;padding:4px 12px;border:0;background:transparent;color:var(--fg-muted);cursor:pointer}
.df-seg button+button{border-left:1px solid var(--fg-line)}
.df-seg button.on{background:var(--fg-text);color:var(--fg-panel);font-weight:600}
.df-seg button:focus-visible{outline:2px solid var(--fg-accent);outline-offset:-2px}
.df-leg{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font-size:12px;color:var(--fg-muted);padding:0 0 8px}
.df-leg span{display:inline-flex;align-items:center;gap:5px}
.df-sw{display:inline-block;width:16px;height:12px;border:1px solid var(--fg-line);border-left-width:4px;border-radius:3px;background:var(--fg-panel)}
.df-sw.T-source{border-left-color:var(--fg-muted)}.df-sw.T-calc{border-left-color:var(--fg-accent)}.df-sw.T-llm{border-left-color:var(--fg-warn)}.df-sw.T-pub{border-left-color:var(--fg-ok)}.df-sw.T-ops{border-left-color:var(--fg-line)}
.df-sw.dash{border-style:dashed;border-left-width:1px}
.df-ln{display:inline-block;width:22px;height:0;border-top:2.5px solid var(--fg-text)}
.df-ln.up{border-color:var(--fg-ok)}.df-ln.dn{border-color:var(--fg-accent)}
.df-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--fg-warn)}
.df-stat{font-size:13px;padding:7px 12px;border:1px solid var(--fg-line);border-radius:8px;background:var(--fg-fill);margin-bottom:10px;line-height:1.5}
.df-stat b{font-weight:600}
.df-stat code,.df-panel code,.df-box code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px;background:var(--fg-panel);border:1px solid var(--fg-line);padding:0 4px;border-radius:4px}
.df-scroll{position:relative;overflow:auto;border:1px solid var(--fg-line);border-radius:10px;background:var(--fg-fill)}
.df-spacer{position:relative}
.df-canvas{position:absolute;left:14px;top:14px;transform-origin:0 0}
.df-wires{position:absolute;left:0;top:0;overflow:visible;pointer-events:none}
.df-wires path.w{fill:none;stroke:var(--fg-muted);stroke-width:1.1;opacity:.42;stroke-linejoin:round}
.df-wires path.a{fill:var(--fg-muted);stroke:none;opacity:.42}
.df-wires g.on path.w{stroke:var(--fg-text);stroke-width:2;opacity:1}
.df-wires g.on path.a{fill:var(--fg-text);opacity:1}
.df-wires g.up path.w{stroke:var(--fg-ok);stroke-width:2.2;opacity:1}
.df-wires g.up path.a{fill:var(--fg-ok);opacity:1}
.df-wires g.dn path.w{stroke:var(--fg-accent);stroke-width:2.2;opacity:1}
.df-wires g.dn path.a{fill:var(--fg-accent);opacity:1}
.df-wires g.dim{opacity:.1}
.df-wires g.off{display:none}
.df-wires g.soft path.w{stroke-dasharray:4 3}
.df-wires g.cw path.w{stroke-width:1.45;opacity:.95}
.df-wires g.cw path.a{opacity:1}
.df-wires g.cw.up path.w{stroke:var(--fg-ok)}.df-wires g.cw.up path.a{fill:var(--fg-ok)}
.df-wires g.cw.dn path.w{stroke:var(--fg-accent)}.df-wires g.cw.dn path.a{fill:var(--fg-accent)}
.df-head{position:absolute;top:0;font-size:12.5px;font-weight:700;border-bottom:2px solid var(--fg-text);padding-bottom:3px;line-height:1.35;color:var(--fg-text)}
.df-head small{display:block;font-weight:400;color:var(--fg-muted);font-size:11px}
.df-grp{position:absolute;font-size:11.5px;font-weight:600;color:var(--fg-muted);cursor:pointer;padding:3px 2px 1px;border-radius:4px;user-select:none}
.df-grp:hover,.df-grp.on{color:var(--fg-accent)}
.df-grp small{font-weight:400;margin-left:4px}
.df-box{position:absolute;background:var(--fg-panel);border:1px solid var(--fg-line);border-radius:8px;z-index:1;font-size:12px;line-height:1.42;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,.05);transition:opacity .12s;color:var(--fg-text)}
.df-box header{padding:6px 9px 6px 8px;border-left:4px solid var(--fg-muted);border-radius:7px}
.df-box.has-cols header{border-bottom:1px solid var(--fg-line);border-radius:7px 7px 0 0}
.df-box.T-calc header{border-left-color:var(--fg-accent)}
.df-box.T-llm header{border-left-color:var(--fg-warn)}
.df-box.T-pub header{border-left-color:var(--fg-ok)}
.df-box.T-ops header{border-left-color:var(--fg-line)}
.df-box.S-plan,.df-box.S-todo,.df-box.S-gap{border-style:dashed}
.df-box.dim{opacity:.2}
.df-box.sel{outline:2px solid var(--fg-text);outline-offset:1px}
.df-box:focus-visible{outline:2px solid var(--fg-accent);outline-offset:1px}
.df-box .nm{font-weight:700;font-size:13px;word-break:break-word}
.df-box.T-source .nm{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;font-weight:600}
.df-box .sch{display:block;color:var(--fg-muted);font-weight:400;font-size:10.5px}
.df-box .bn{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10.5px;color:var(--fg-muted)}
.df-box .gr{color:var(--fg-text);font-size:11.5px}
.df-box .gr i{font-style:normal;color:var(--fg-muted);margin-right:5px;font-size:10.5px}
.df-box .fl{color:var(--fg-muted);font-size:11px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.df-box .kd{display:inline-block;font-size:10.5px;font-weight:600;color:var(--fg-accent);background:var(--fg-accent-bg);border-radius:4px;padding:0 5px;margin-right:5px}
.df-box .tg{margin-top:3px;display:flex;flex-wrap:wrap;gap:4px}
.df-tag{display:inline-block;font-size:10.5px;font-weight:600;border-radius:999px;padding:0 7px;white-space:nowrap}
.df-tag.llm,.df-tag.S-plan,.df-tag.S-todo{background:var(--fg-warn-bg);color:var(--fg-warn)}
.df-tag.S-ok{background:var(--fg-ok-bg);color:var(--fg-ok)}
.df-tag.S-has{background:var(--fg-fill);color:var(--fg-muted)}
.df-tag.S-gap{background:var(--fg-no-bg);color:var(--fg-no)}
.df-box ul{list-style:none;margin:0;padding:3px 0;max-width:none}
.df-box li{display:flex;gap:5px;align-items:center;height:19px;padding:0 9px 0 7px;margin:0;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px}
.df-box li .cn{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.df-box li .ct{margin-left:auto;color:var(--fg-muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:44%;padding-left:6px}
.df-box li.x{display:none}
.df-box li.x.show,.df-canvas.all .df-box li.x{display:flex}
.df-canvas.all .df-box li.sum:not(.keep){display:none}
.df-box li.ai{color:var(--fg-warn);font-weight:600}
.df-box li.ex{color:var(--fg-muted);font-style:italic}
.df-box li.as{font-style:italic}
.df-box li.nd .cn{font-family:inherit;font-style:italic}
.df-box li.q .cn::after{content:"";display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--fg-warn);margin-left:5px;vertical-align:middle}
.df-box li[data-c]{cursor:pointer}
.df-box li[data-c]:hover{background:var(--fg-fill)}
.df-box li.cu{background:var(--fg-ok-bg);box-shadow:inset 3px 0 0 var(--fg-ok)}
.df-box li.cd{background:var(--fg-accent-bg);box-shadow:inset 3px 0 0 var(--fg-accent)}
.df-box li.cs,.df-box li.cs:hover{background:var(--fg-text);color:var(--fg-panel)}
.df-box li.cs .ct{color:var(--fg-panel)}
.df-box li.cs .df-ek{stroke:var(--fg-panel)}
.df-box li.sum{font-family:inherit;color:var(--fg-muted);font-size:11px;height:auto;min-height:19px;line-height:1.35;padding-top:2px;padding-bottom:2px;align-items:flex-start}
.df-ek{width:12px;height:12px;flex:none;fill:none;stroke:var(--fg-text);stroke-width:1.6}
.df-nk{width:12px;flex:none}
.df-panel{position:fixed;right:16px;bottom:16px;width:min(620px,calc(100vw - 32px));max-height:74vh;overflow:auto;background:var(--fg-panel);color:var(--fg-text);border:1px solid var(--fg-line);border-radius:12px;box-shadow:0 10px 34px rgba(0,0,0,.28);z-index:60;font-size:13px;line-height:1.55}
.df-panel .ph{position:sticky;top:0;display:flex;justify-content:space-between;gap:10px;align-items:baseline;padding:10px 14px;background:var(--fg-fill);border-bottom:1px solid var(--fg-line);font-weight:700;font-size:14px;z-index:1}
.df-panel .ph button{font:inherit;font-size:12.5px;font-weight:600;border:0;background:transparent;color:var(--fg-accent);cursor:pointer}
.df-panel .pb{padding:10px 14px 14px}
.df-panel dl{display:grid;grid-template-columns:108px minmax(0,1fr);gap:5px 12px;margin:0}
.df-panel dt{color:var(--fg-muted);font-size:12px}
.df-panel dd{margin:0}
.df-panel h4{margin:14px 0 4px;font-size:13px}
.df-panel h4 small{font-weight:400;color:var(--fg-muted);margin-left:6px}
.df-panel .df-tbl{overflow-x:auto;border:1px solid var(--fg-line);border-radius:8px;margin-top:4px}
.df-panel table{min-width:0;width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px}
.df-panel th,.df-panel td{padding:4px 8px;text-align:left;vertical-align:top;border-bottom:1px solid var(--fg-line);word-break:break-word}
.df-panel tr:last-child td{border-bottom:0}
.df-panel th{font-size:11.5px;font-weight:600;color:var(--fg-muted);background:var(--fg-fill)}
.df-panel th:nth-child(1){width:33%}.df-panel th:nth-child(2){width:18%}.df-panel th:nth-child(3){width:14%}
.df-panel td.c{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px}
.df-panel td.ai{color:var(--fg-warn);font-weight:600}
.df-panel tr[data-col]{cursor:pointer}
.df-panel tr[data-col]:hover td{background:var(--fg-fill)}
.df-panel .rs{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;color:var(--fg-muted);margin-top:3px;word-break:break-all;line-height:1.45}
.df-panel .lg{font-size:11.5px;margin-top:3px;color:var(--fg-text)}
.df-pc{font:inherit;font-size:12px;border:1px solid var(--fg-line);border-left-width:3px;border-radius:5px;background:var(--fg-panel);color:var(--fg-text);padding:1px 8px;margin:0 4px 4px 0;cursor:pointer}
.df-pc.T-source{border-left-color:var(--fg-muted);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px}
.df-pc.T-calc{border-left-color:var(--fg-accent)}.df-pc.T-llm{border-left-color:var(--fg-warn)}.df-pc.T-pub{border-left-color:var(--fg-ok)}
.df-pc.nd{border-style:dashed}
.df-pc:hover{background:var(--fg-fill)}
.df-cf{display:inline-block;font-size:10.5px;font-weight:600;border-radius:999px;padding:0 7px;white-space:nowrap}
.df-cf.ok{background:var(--fg-ok-bg);color:var(--fg-ok)}.df-cf.sg{background:var(--fg-fill);color:var(--fg-muted)}.df-cf.nd,.df-cf.no{background:var(--fg-warn-bg);color:var(--fg-warn)}
.df-mu{color:var(--fg-muted)}
.df-tabs{display:flex;gap:6px;margin:18px 0 0;border-bottom:1px solid var(--fg-line)}
.df-tabs button{font:inherit;font-size:14px;font-weight:600;padding:8px 18px;border:1px solid transparent;border-bottom:none;border-radius:10px 10px 0 0;background:transparent;color:var(--fg-muted);cursor:pointer;margin-bottom:-1px}
.df-tabs button:hover{color:var(--fg-text)}
.df-tabs button[aria-selected="true"]{background:var(--fg-panel);color:var(--fg-text);border-color:var(--fg-line);box-shadow:inset 0 3px 0 var(--fg-accent)}
.df-tabs button:focus-visible{outline:2px solid var(--fg-accent);outline-offset:2px}
.df-wide{max-width:2000px;margin:0 auto;padding:12px 0 40px}
@media print{.df-panel{display:none!important}.df-scroll{overflow:visible}}
"""

LINEAGE_JS = f"""<script id="{LINEAGE_SCRIPT_ID}">
(function () {{
  const NS = 'http://www.w3.org/2000/svg', SEP = '\\u0001';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
  const rich = s => esc(s).replace(/&lt;code&gt;(.*?)&lt;\\/code&gt;/g, '<code>$1</code>').replace(/`([^`]+)`/g, '<code>$1</code>');
  const KEY = '<svg class="df-ek" viewBox="0 0 16 16" aria-label="키"><circle cx="4.8" cy="8" r="3"/><path d="M7.8 8H15M12.4 8v3M14.6 8v2.2"/></svg>';
  const CF = {{
    ok: ['확인', '원천·문서가 표·열을 직접 가리킨다'],
    sg: ['제안', '열 이름·설명을 보고 고른 제안(실데이터 대조 전)'],
    nd: ['열 미정', '읽을 표는 정해졌으나 열이 아직 정해지지 않았다'],
    no: ['재료 없음', '읽을 곳이 아직 정해지지 않았다']
  }};
  const reach = (start, adj) => {{
    const seen = new Set(), st = [...start];
    while (st.length) {{ const x = st.pop(); (adj[x] || []).forEach(y => {{ if (!seen.has(y)) {{ seen.add(y); st.push(y); }} }}); }}
    return seen;
  }};

  function initFigure(fig) {{
    if (fig.dataset.dfReady) return;
    fig.dataset.dfReady = '1';
    const dataEl = fig.querySelector('.df-lineage-data');
    if (!dataEl) return;
    const G = JSON.parse(dataEl.textContent);
    const W = G.boxWidth || 236, GAPX = G.gapX || 96, GAPY = G.gapY || 10, TOP = 46, PAD = 14;
    const cv = fig.querySelector('.df-canvas'), svg = fig.querySelector('.df-wires'),
      scroller = fig.querySelector('.df-scroll'), spacer = fig.querySelector('.df-spacer'),
      panel = fig.querySelector('.df-panel'), stat = fig.querySelector('.df-stat');
    const N = {{}}; G.nodes.forEach(n => N[n.id] = n);
    const SOFT = new Set((G.soft || []).map(e => e[0] + SEP + e[1]));
    const out = {{}}, inn = {{}};
    G.edges.forEach(([a, b]) => {{ (out[a] = out[a] || []).push(b); (inn[b] = inn[b] || []).push(a); }});
    const cidOf = (t, c) => t + SEP + c, tblOf = x => x.split(SEP)[0];
    const allCols = n => (n.cols || []).concat(n.extra || []);
    const C = {{}}, cin = {{}}, cout = {{}}, LI = {{}};
    G.nodes.forEach(n => allCols(n).forEach(c => {{ const x = cidOf(n.id, c.c); if (!C[x]) C[x] = {{ n, c }}; }}));
    Object.keys(C).forEach(x => (C[x].c.s || []).forEach(([t, col]) => {{
      const s = cidOf(t, col);
      if (!C[s] || s === x) return;
      (cin[x] = cin[x] || []).push(s); (cout[s] = cout[s] || []).push(x);
    }}));

    const EL = {{}}, GRP = {{}}, HEAD = [];
    const state = {{ hover: null, pin: null, src: null, col: null }};
    let fit = fig.dataset.defaultFit === '1';

    function nameHTML(n) {{
      const i = n.name.lastIndexOf('.');
      if (n.tone === 'source' && i > 0) return '<span class="sch">' + esc(n.name.slice(0, i)) + '</span>' + esc(n.name.slice(i + 1));
      return esc(n.name);
    }}

    G.nodes.forEach(n => {{
      const b = document.createElement('div');
      const rows = (n.cols || []).map(c => [c, false]).concat((n.extra || []).map(c => [c, true]));
      b.className = 'df-box T-' + n.tone + (n.st ? ' S-' + n.st : '') + (rows.length ? ' has-cols' : '');
      b.dataset.id = n.id; b.tabIndex = 0; b.setAttribute('role', 'button'); b.style.width = W + 'px';
      const tags = [];
      if (n.tone === 'llm') tags.push('<span class="df-tag llm">LLM</span>');
      if (n.st && n.stLabel) tags.push('<span class="df-tag S-' + esc(n.st) + '">' + esc(n.stLabel) + '</span>');
      if (n.proposed) tags.push('<span class="df-tag S-has">열 = 제안</span>');
      if (n.wait && n.wait.length) tags.push('<span class="df-tag S-todo">재료 대기 ' + n.wait.length + '</span>');
      (n.tags || []).forEach(tg => tags.push('<span class="df-tag S-has">' + esc(tg) + '</span>'));
      let h = '<header><div class="nm">' + nameHTML(n) + '</div>'
        + (n.bain ? '<div class="bn">' + esc(n.bain) + '</div>' : '')
        + (n.grain ? '<div class="gr"><i>한 줄</i>' + rich(n.grain) + '</div>' : '')
        + ((n.kind || n.flow) ? '<div class="fl">' + (n.kind ? '<span class="kd">' + esc(n.kind) + '</span>' : '') + rich(n.flow || '') + '</div>' : '')
        + (tags.length ? '<div class="tg">' + tags.join('') + '</div>' : '') + '</header>';
      if (rows.length) {{
        const cnt = {{}}; rows.forEach(([c, ex]) => {{ const k = ex ? '조립' : (c.k || '칸'); cnt[k] = (cnt[k] || 0) + 1; }});
        const always = !!n.always;
        h += '<ul>' + rows.map(([c, ex]) => {{
          const key = c.k === '키', cls = [(key || always) ? 'v' : 'x'];
          if (c.ly === 'infer' || c.ly === 'llm') cls.push('ai');
          if (c.ly === 'silver 추출' || c.ly === 'extract') cls.push('ex');
          if (ex) cls.push('as');
          if (c.nd) cls.push('nd');
          if (c.cf === 'nd' || c.cf === 'no') cls.push('q');
          const right = n.tone === 'source' ? (c.nd ? '가칭' : (c.m || c.t || '')) : (ex ? '조립' : (c.t || ''));
          return '<li class="' + cls.join(' ') + '" data-c="' + esc(c.c) + '" title="' + esc(c.m || '') + '">'
            + (key ? KEY : '<span class="df-nk"></span>') + '<span class="cn">' + esc(c.c) + '</span><span class="ct">' + esc(right) + '</span></li>';
        }}).join('');
        if (n.tone === 'source') {{
          const nd = rows.filter(([c]) => c.nd).length, us = rows.length - nd, parts = [];
          if (n.total != null) parts.push('쓰는 열 ' + us + ' · 전체 ' + n.total);
          else if (us) parts.push('쓰는 열 ' + us);
          if (nd) parts.push('정해야 할 칸 ' + nd + ' (가칭)');
          if (parts.length) h += '<li class="sum keep"><span class="df-nk"></span>' + parts.join(' · ') + '</li>';
        }} else {{
          const rest = Object.keys(cnt).filter(k => k !== '키' && !always);
          if (rest.length) h += '<li class="sum"><span class="df-nk"></span>그 밖 ' + rest.map(k => esc(k) + ' ' + cnt[k]).join(' · ') + '</li>';
        }}
        h += '</ul>';
      }}
      b.innerHTML = h; cv.appendChild(b); EL[n.id] = b;
      b.querySelectorAll('li[data-c]').forEach(li => {{ LI[cidOf(n.id, li.dataset.c)] = li; }});
    }});

    G.lanes.forEach((ln, i) => {{
      const h = document.createElement('div'); h.className = 'df-head'; h.style.width = W + 'px';
      h.innerHTML = esc(ln.title) + (ln.sub ? '<small>' + esc(ln.sub) + '</small>' : '');
      cv.appendChild(h); HEAD[i] = h;
    }});

    const groups = [];
    if (G.lanes.length) {{
      G.lanes[0].ids.forEach(id => {{ const g = N[id] && N[id].group; if (g && !groups.includes(g)) groups.push(g); }});
    }}
    groups.forEach(g => {{
      const d = document.createElement('div'); d.className = 'df-grp'; d.dataset.g = g; d.style.width = W + 'px';
      const cnt = G.nodes.filter(x => x.group === g).length;
      d.innerHTML = esc(g) + '<small>표 ' + cnt + '개 · 누르면 파급 흐름</small>';
      cv.appendChild(d); GRP[g] = d;
    }});

    const srcWrap = fig.querySelector('.df-src-wrap'), srcBar = fig.querySelector('.df-src');
    if (groups.length && srcBar) {{
      groups.forEach(g => {{ const b = document.createElement('button'); b.type = 'button'; b.dataset.g = g; b.textContent = g; srcBar.appendChild(b); }});
    }} else if (srcWrap) {{ srcWrap.hidden = true; }}

    const gT = document.createElementNS(NS, 'g'), gC = document.createElementNS(NS, 'g');
    svg.appendChild(gT); svg.appendChild(gC);

    function place() {{
      let maxH = 0;
      G.lanes.forEach((ln, i) => {{
        const x = i * (W + GAPX);
        HEAD[i].style.left = x + 'px';
        const want = {{}};
        if (i > 0) {{
          ln.ids.forEach(id => {{
            const ys = (inn[id] || []).filter(a => N[a] && N[a].lane < i).map(a => EL[a].offsetTop + 17);
            want[id] = ys.length ? ys.reduce((p, c) => p + c, 0) / ys.length - 17 : Infinity;
          }});
        }}
        let y = TOP, last = null;
        ln.ids.forEach(id => {{
          const b = EL[id], n = N[id];
          if (i === 0 && n.group && n.group !== last && GRP[n.group]) {{
            const g = GRP[n.group]; g.style.left = x + 'px'; g.style.top = y + 'px'; y += (g.offsetHeight || 20) + 4; last = n.group;
          }}
          if (i > 0 && want[id] !== Infinity) y = Math.max(y, Math.round(want[id]));
          b.style.left = x + 'px'; b.style.top = y + 'px'; y += (b.offsetHeight || 54) + GAPY;
        }});
        maxH = Math.max(maxH, y);
      }});
      const w = Math.max(320, G.lanes.length * (W + GAPX) - GAPX + 60);
      cv.style.width = w + 'px'; cv.style.height = maxH + 'px';
      svg.setAttribute('width', w); svg.setAttribute('height', maxH);
    }}

    function applyFit() {{
      const w = (cv.offsetWidth || 800) + PAD * 2, hgt = (cv.offsetHeight || 400) + PAD * 2;
      const avail = scroller.clientWidth || w;
      const k = (fit && avail > 0) ? Math.min(1, avail / w) : 1;
      cv.style.transform = k < 1 ? 'scale(' + k + ')' : '';
      spacer.style.width = Math.ceil(w * k) + 'px'; spacer.style.height = Math.ceil(hgt * k) + 'px';
    }}

    const slot = {{}};
    G.lanes.forEach(ln => ln.ids.forEach((id, i) => slot[id] = i));
    const anchor = id => {{ const b = EL[id]; return {{ l: b.offsetLeft, r: b.offsetLeft + W, y: b.offsetTop + 17 }}; }};
    function pathOf(a, b) {{
      const A = anchor(a), B = anchor(b), s = slot[a] || 0;
      if (N[a].lane >= N[b].lane) {{
        const xm = Math.max(A.r, B.r) + 16 + (s % 5) * 6;
        return {{ d: `M${{A.r}},${{A.y}} H${{xm}} V${{B.y}} H${{B.r + 6}}`, ar: `M${{B.r}},${{B.y}} l7,-3.6 v7.2 z` }};
      }}
      const xm = B.l - 16 - (s % 9) * 7;
      return {{ d: `M${{A.r}},${{A.y}} H${{xm}} V${{B.y}} H${{B.l - 6}}`, ar: `M${{B.l}},${{B.y}} l-7,-3.6 v7.2 z` }};
    }}
    function colAnchor(x) {{
      const li = LI[x], b = EL[tblOf(x)];
      return {{ l: b.offsetLeft, r: b.offsetLeft + W, y: b.offsetTop + li.offsetTop + (li.offsetHeight || 19) / 2, lane: N[tblOf(x)].lane, b }};
    }}
    function colPath(s, d, i) {{
      const A = colAnchor(s), B = colAnchor(d);
      if (A.b === B.b) {{
        const xm = A.r + 9 + (i % 4) * 4;
        return {{ d: `M${{A.r}},${{A.y}} H${{xm}} V${{B.y}} H${{B.r + 5}}`, ar: `M${{B.r}},${{B.y}} l6,-3 v6 z` }};
      }}
      if (A.lane >= B.lane) {{
        const xm = Math.max(A.r, B.r) + 22 + (i % 6) * 5;
        return {{ d: `M${{A.r}},${{A.y}} H${{xm}} V${{B.y}} H${{B.r + 5}}`, ar: `M${{B.r}},${{B.y}} l6,-3 v6 z` }};
      }}
      const xm = B.l - 12 - (i % 11) * 6;
      return {{ d: `M${{A.r}},${{A.y}} H${{xm}} V${{B.y}} H${{B.l - 5}}`, ar: `M${{B.l}},${{B.y}} l-6,-3 v6 z` }};
    }}
    function wire(parent, p, cls) {{
      const g = document.createElementNS(NS, 'g');
      if (cls) g.setAttribute('class', cls);
      g.innerHTML = `<path class="w" d="${{p.d}}"/><path class="a" d="${{p.ar}}"/>`;
      parent.appendChild(g);
    }}

    const DEFAULT_STAT = G.defaultStat || '표를 누르면 읽는 쪽(초록·상류)과 읽히는 쪽(파랑·하류)이 끝까지 이어지고, 열 사이의 연결선이 나타납니다. <b>열을 누르면</b> 원천 열까지 거슬러 올라가는 계보와 계산 로직이 열립니다.';

    const hasSourceTone = G.nodes.some(n => n.tone === 'source');
    function focusState() {{
      const f = {{ keep: null, cls: null, rows: {{}}, cw: [], off: new Set(), sel: null, stat: DEFAULT_STAT }};
      if (state.col && C[state.col]) {{
        const x = state.col, U = reach([x], cin), D = reach([x], cout);
        f.keep = new Set([x, ...U, ...D].map(tblOf));
        f.cls = () => 'off';
        U.forEach(y => f.rows[y] = 'cu'); D.forEach(y => f.rows[y] = 'cd'); f.rows[x] = 'cs';
        new Set([x, ...U]).forEach(y => (cin[y] || []).forEach(s => f.cw.push([s, y, 'up'])));
        new Set([x, ...D]).forEach(y => (cout[y] || []).forEach(d => f.cw.push([y, d, 'dn'])));
        const srcs = [...U].filter(y => hasSourceTone ? C[y].n.tone === 'source' : !(cin[y] && cin[y].length));
        f.stat = '<b>' + esc(C[x].n.name) + ' . ' + esc(C[x].c.c) + '</b> — 바로 읽는 열 ' + (cin[x] || []).length + '개 · 거슬러 올라가면 원천 열 '
          + srcs.length + '개 (표 ' + new Set(srcs.map(tblOf)).size + '개) · 이 열을 읽는 하류 열 ' + D.size + '개';
      }} else if (state.pin && N[state.pin]) {{
        const id = state.pin, up = reach([id], inn), dn = reach([id], out);
        const U = new Set([id, ...up]), D = new Set([id, ...dn]);
        f.keep = new Set([...U, ...D]); f.sel = id;
        f.cls = (a, b) => (U.has(a) && U.has(b)) ? 'up' : (D.has(a) && D.has(b)) ? 'dn' : 'dim';
        allCols(N[id]).forEach(c => {{
          const x = cidOf(id, c.c); f.rows[x] = f.rows[x] || 'sh';
          (cin[x] || []).forEach(s => {{ if (tblOf(s) !== id) {{ f.rows[s] = 'cu'; f.cw.push([s, x, 'up']); f.off.add(tblOf(s) + SEP + id); }} }});
        }});
        f.stat = '<b>' + esc(N[id].name) + '</b> — 읽는 상류 표 ' + up.size + '개 · 이 표를 읽는 하류 표 ' + dn.size + '개'
          + (f.cw.length ? ' · 직접 이어진 열 연결 ' + f.cw.length + '개' : '');
      }} else if (state.src) {{
        const ids = G.nodes.filter(n => n.group === state.src).map(n => n.id), dn = reach(ids, out);
        f.keep = new Set([...ids, ...dn]);
        f.cls = (a, b) => (f.keep.has(a) && f.keep.has(b)) ? 'dn' : 'dim';
        const hit = [...dn].filter(x => !ids.includes(x));
        f.stat = '<b>' + esc(state.src) + '</b> 갱신 시 파급되는 하류 표 ' + hit.length + '개 (전체 관련 표 ' + f.keep.size + '개)';
      }} else if (state.hover && N[state.hover]) {{
        const id = state.hover;
        f.keep = new Set([id, ...(inn[id] || []), ...(out[id] || [])]);
        f.cls = (a, b) => (a === id || b === id) ? 'on' : 'dim';
        f.stat = '<b>' + esc(N[id].name) + '</b> — 직접 읽는 표 ' + (inn[id] || []).length + '개 · 직접 읽히는 표 ' + (out[id] || []).length + '개 (클릭하면 끝까지 추적)';
      }}
      return f;
    }}

    function refresh() {{
      if (fig.offsetParent === null && scroller.clientWidth === 0) return;
      const f = focusState();
      Object.keys(LI).forEach(x => {{
        const li = LI[x], r = f.rows[x];
        li.classList.remove('show', 'cu', 'cd', 'cs');
        if (r) {{ li.classList.add('show'); if (r !== 'sh') li.classList.add(r); }}
      }});
      place();
      gT.innerHTML = ''; gC.innerHTML = '';
      G.edges.forEach(([a, b]) => {{
        if (!EL[a] || !EL[b]) return;
        const c = ((f.cls ? (f.off.has(a + SEP + b) ? 'off' : f.cls(a, b)) : '') + (SOFT.has(a + SEP + b) ? ' soft' : '')).trim();
        wire(gT, pathOf(a, b), c);
      }});
      f.cw.forEach(([s, d, k], i) => {{ if (LI[s] && LI[d]) wire(gC, colPath(s, d, i), 'cw ' + k); }});
      Object.values(EL).forEach(b => {{
        b.classList.toggle('dim', !!f.keep && !f.keep.has(b.dataset.id));
        b.classList.toggle('sel', f.sel === b.dataset.id);
      }});
      Object.values(GRP).forEach(g => g.classList.toggle('on', g.dataset.g === state.src));
      fig.querySelectorAll('.df-src button').forEach(b => b.classList.toggle('on', b.dataset.g === state.src));
      fig.querySelectorAll('.df-mode button').forEach(b => b.classList.toggle('on', (b.dataset.m === 'all') === cv.classList.contains('all')));
      fig.querySelectorAll('.df-zoom button').forEach(b => b.classList.toggle('on', (b.dataset.z === 'fit') === fit));
      stat.innerHTML = f.stat;
      applyFit();
    }}

    const cfChip = cf => CF[cf] ? '<span class="df-cf ' + cf + '" title="' + esc(CF[cf][1]) + '">' + CF[cf][0] + '</span>' : '';
    const tblChip = id => '<button type="button" class="df-pc T-' + N[id].tone + '" data-go="' + esc(id) + '">' + esc(N[id].name) + '</button>';
    const colChip = x => '<button type="button" class="df-pc T-' + C[x].n.tone + (C[x].c.nd ? ' nd' : '') + '" data-col="' + esc(x) + '">' + esc(C[x].n.name) + ' . <b>' + esc(C[x].c.c) + '</b></button>';
    const srcText = (id, c) => (c.s || []).map(([t, col]) => (t === id ? '이 표' : t) + '.' + col).concat((c.g || []).map(g => '설정:' + g)).join(' · ');

    function colTable(n, cols) {{
      const isSrc = n.tone === 'source', isPub = n.tone === 'pub';
      const third = isPub ? '채우는 층' : (isSrc ? '설명' : '구분');
      return '<div class="df-tbl"><table><tr><th>열</th><th>타입</th><th>' + third + '</th><th>' + (isSrc ? '쓰이는 곳' : '뜻 · 읽는 열 · 로직') + '</th></tr>'
        + cols.map(c => {{
          const x = cidOf(n.id, c.c), src = srcText(n.id, c);
          const k = isPub ? (c.ly || '') : (isSrc ? (c.nd ? '(가칭)' : (c.m || '')) : (c.k || ''));
          const last = isSrc
            ? ((cout[x] || []).map(d => esc(C[d].n.name + '.' + C[d].c.c)).join(' · ') || '<span class="df-mu">—</span>')
            : esc(c.m || '') + (src ? '<div class="rs">← ' + esc(src) + '</div>' : '') + (c.lg ? '<div class="lg">' + rich(c.lg) + '</div>' : '');
          return '<tr data-col="' + esc(x) + '"><td class="c' + ((c.ly === 'infer' || c.ly === 'llm') ? ' ai' : '') + '">' + esc(c.c) + (c.cf && c.cf !== 'sg' ? ' ' + cfChip(c.cf) : '') + '</td><td class="c">' + esc(c.t || '') + '</td><td>'
            + esc(k) + '</td><td>' + last + '</td></tr>';
        }}).join('') + '</table></div>';
    }}

    function openPanel(id) {{
      const n = N[id];
      const chips = ids => ids.length ? ids.map(tblChip).join('') : '<span class="df-mu">없음</span>';
      let h = '<dl>';
      const row = (k, v) => {{ if (v) h += '<dt>' + esc(k) + '</dt><dd>' + v + '</dd>'; }};
      row('층 · 구분', esc(n.layerLabel || '') + (n.kind ? ' · ' + esc(n.kind) : ''));
      row('한 줄', n.grain ? rich(n.grain) : '');
      row('키 (번호)', n.key ? rich(n.key) : '');
      row('생성 계기', n.trigger ? rich(n.trigger) : '');
      row('LLM 호출', n.llm ? rich(n.llm) : '');
      row('사건 날짜', n.edate ? rich(n.edate) : '');
      row('갱신 방식', n.how ? rich(n.how) : '');
      row('박자', n.cadence ? rich(n.cadence) : '');
      row('상태', n.stText ? rich(n.stText) : '');
      row('참조', n.bain ? esc(n.bain) : '');
      (n.meta || []).forEach(([k, v]) => row(k, rich(v)));
      row('읽는 표', chips(inn[id] || []));
      row('읽히는 표', chips(out[id] || []));
      if (n.wait && n.wait.length) row('미구현 재료', n.wait.map(esc).join(' · '));
      h += '</dl>';
      if (n.cols && n.cols.length) {{
        h += '<h4>열 ' + n.cols.length + '개<small>행을 누르면 열 계보가 열립니다</small></h4>' + colTable(n, n.cols);
      }}
      if (n.extra && n.extra.length) {{
        h += '<h4>조립 열 ' + n.extra.length + '개</h4>' + colTable(n, n.extra);
      }}
      panel.innerHTML = '<div class="ph"><span>' + esc(n.name) + '</span><button type="button" data-close>닫기</button></div><div class="pb">' + h + '</div>';
      panel.hidden = false; panel.scrollTop = 0;
    }}

    function openColPanel(x) {{
      const {{ n, c }} = C[x], U = reach([x], cin), D = reach([x], cout);
      let h = '<dl>';
      const row = (k, v) => {{ if (v) h += '<dt>' + esc(k) + '</dt><dd>' + v + '</dd>'; }};
      row('표', tblChip(n.id));
      row('타입', c.t ? '<code>' + esc(c.t) + '</code>' : '');
      row('뜻', esc(c.m || ''));
      row('채우는 층', esc(c.ly || n.layerLabel || '') + (c.k ? ' · ' + esc(c.k) : ''));
      row('확실도', c.cf && CF[c.cf] ? cfChip(c.cf) + ' ' + esc(CF[c.cf][1]) : '');
      row('로직', c.lg ? rich(c.lg) : '');
      row('설정값', (c.g || []).length ? c.g.map(esc).join(' · ') : '');
      const direct = cin[x] || [];
      row('읽는 열', direct.length ? direct.map(colChip).join('') : '<span class="df-mu">원천 입력 또는 설정값</span>');
      row('읽히는 열', (cout[x] || []).length ? (cout[x] || []).map(colChip).join('') : '<span class="df-mu">없음</span>');
      h += '</dl>';
      const srcs = [...U].filter(y => C[y].n.tone === 'source').sort();
      if (n.tone !== 'source' && srcs.length) {{
        h += '<h4>거슬러 올라가면 닿는 원천 열 ' + srcs.length + '개</h4><div class="df-tbl"><table><tr><th>원천 표</th><th>열</th><th>설명</th></tr>'
          + srcs.map(y => '<tr data-col="' + esc(y) + '"><td class="c">' + esc(C[y].n.name) + '</td><td class="c">' + esc(C[y].c.c) + '</td><td>' + (C[y].c.nd ? '<span class="df-mu">(가칭)</span>' : esc(C[y].c.m || '')) + '</td></tr>').join('')
          + '</table></div>';
      }}
      const pubs = [...D].filter(y => C[y].n.tone === 'pub');
      if (pubs.length && D.size > (cout[x] || []).length) {{
        h += '<h4>끝까지 가면 닿는 게시 칸 ' + pubs.length + '개</h4><p>' + pubs.map(colChip).join('') + '</p>';
      }}
      panel.innerHTML = '<div class="ph"><span>' + esc(n.name) + ' . <code>' + esc(c.c) + '</code></span><button type="button" data-close>닫기</button></div><div class="pb">' + h + '</div>';
      panel.hidden = false; panel.scrollTop = 0;
    }}

    function pin(id, scroll) {{
      state.pin = id; state.src = null; state.hover = null; state.col = null;
      if (id) openPanel(id); else panel.hidden = true;
      refresh();
      if (id && scroll && EL[id]) EL[id].scrollIntoView({{ block: 'center', inline: 'center', behavior: 'smooth' }});
    }}
    function pinCol(x, scroll) {{
      state.col = x; state.pin = null; state.src = null; state.hover = null;
      if (x) openColPanel(x); else panel.hidden = true;
      refresh();
      if (x && scroll && LI[x]) LI[x].scrollIntoView({{ block: 'center', inline: 'center', behavior: 'smooth' }});
    }}
    function pickSrc(g) {{ state.src = state.src === g ? null : g; state.pin = null; state.col = null; panel.hidden = true; refresh(); }}
    function clearAll() {{ state.src = null; state.col = null; pin(null); }}

    cv.addEventListener('mouseover', e => {{
      if (state.pin || state.src || state.col) return;
      const b = e.target.closest('.df-box'), id = b ? b.dataset.id : null;
      if (id !== state.hover) {{ state.hover = id; refresh(); }}
    }});
    cv.addEventListener('mouseleave', () => {{ if (state.hover) {{ state.hover = null; refresh(); }} }});
    cv.addEventListener('click', e => {{
      const g = e.target.closest('.df-grp'); if (g) {{ pickSrc(g.dataset.g); return; }}
      const li = e.target.closest('li[data-c]');
      if (li) {{ const x = cidOf(li.closest('.df-box').dataset.id, li.dataset.c); pinCol(state.col === x ? null : x); return; }}
      const b = e.target.closest('.df-box');
      if (b) pin(state.pin === b.dataset.id ? null : b.dataset.id); else if (state.pin || state.src || state.col) clearAll();
    }});
    cv.addEventListener('keydown', e => {{
      if (e.key !== 'Enter' && e.key !== ' ') return;
      const b = e.target.closest('.df-box'); if (b) {{ e.preventDefault(); pin(state.pin === b.dataset.id ? null : b.dataset.id); }}
    }});
    document.addEventListener('keydown', e => {{ if (e.key === 'Escape' && !panel.hidden) clearAll(); }});
    panel.addEventListener('click', e => {{
      if (e.target.closest('[data-close]')) {{ clearAll(); return; }}
      const go = e.target.closest('[data-go]'); if (go) {{ pin(go.dataset.go, true); return; }}
      const col = e.target.closest('[data-col]'); if (col && C[col.dataset.col]) pinCol(col.dataset.col, true);
    }});
    if (srcBar) srcBar.addEventListener('click', e => {{ const b = e.target.closest('button'); if (b) pickSrc(b.dataset.g); }});
    fig.querySelector('.df-mode').addEventListener('click', e => {{
      const b = e.target.closest('button'); if (!b) return;
      cv.classList.toggle('all', b.dataset.m === 'all'); refresh();
    }});
    fig.querySelector('.df-zoom').addEventListener('click', e => {{
      const b = e.target.closest('button'); if (!b) return;
      fit = b.dataset.z === 'fit'; refresh();
    }});

    function applyQuery(q) {{
      if (q.get('mode') === 'all') cv.classList.add('all');
      if (q.get('fit') === '1') fit = true;
      if (q.get('fit') === '0') fit = false;
      refresh();
      const col = (q.get('col') || '').split('::');
      if (col.length === 2 && C[cidOf(col[0], col[1])]) pinCol(cidOf(col[0], col[1]), false);
      else if (q.get('pin') && N[q.get('pin')]) pin(q.get('pin'), false);
      else if (q.get('src') && GRP[q.get('src')]) pickSrc(q.get('src'));
    }}
    fig._dfRefresh = refresh;
    fig._dfApplyQuery = applyQuery;

    if (typeof ResizeObserver !== 'undefined') {{
      let lastW = 0;
      new ResizeObserver(() => {{
        const w = scroller.clientWidth;
        if (w > 0 && w !== lastW) {{ lastW = w; refresh(); }}
      }}).observe(scroller);
    }} else {{
      window.addEventListener('resize', refresh);
    }}
    refresh();
  }}

  function initTabs(bar) {{
    if (bar.dataset.dfReady) return;
    bar.dataset.dfReady = '1';
    const tabId = bar.dataset.dfTabs;
    const panels = {{ doc: document.getElementById('tab-doc'), [tabId]: document.getElementById(tabId) }};
    function show(which) {{
      Object.keys(panels).forEach(k => {{
        if (!panels[k]) return;
        panels[k].hidden = k !== which;
        const btn = bar.querySelector('[data-tab="' + k + '"]');
        if (btn) btn.setAttribute('aria-selected', String(k === which));
        if (k !== which) panels[k].querySelectorAll('.df-panel').forEach(p => p.hidden = true);
      }});
      if (panels[which]) panels[which].querySelectorAll('.fig-lineage').forEach(f => {{ if (f._dfRefresh) requestAnimationFrame(f._dfRefresh); }});
    }}
    bar.addEventListener('click', e => {{
      const b = e.target.closest('[data-tab]'); if (!b) return;
      show(b.dataset.tab);
      if (typeof history !== 'undefined' && history.replaceState) {{
        history.replaceState(null, '', b.dataset.tab === 'doc' ? location.pathname + location.search : '#' + b.dataset.tab);
      }}
    }});
    document.addEventListener('click', e => {{
      const a = e.target.closest('a[href^="#' + tabId + '"]');
      if (a) {{ e.preventDefault(); location.hash = a.getAttribute('href'); syncHash(); window.scrollTo(0, 0); }}
    }});
    function syncHash() {{
      const raw = decodeURIComponent((typeof location !== 'undefined' && location.hash) || '');
      if (raw === '#' + tabId || raw.startsWith('#' + tabId + '?')) {{
        show(tabId);
        const q = new URLSearchParams(raw.split('?')[1] || '');
        requestAnimationFrame(() => panels[tabId].querySelectorAll('.fig-lineage').forEach(f => f._dfApplyQuery && f._dfApplyQuery(q)));
      }}
    }}
    window.addEventListener('hashchange', syncHash);
    syncHash();
  }}

  function boot() {{
    document.querySelectorAll('figure.fig-lineage').forEach(initFigure);
    document.querySelectorAll('.df-tabs[data-df-tabs]').forEach(initTabs);
    const raw = decodeURIComponent((typeof location !== 'undefined' && location.hash) || '');
    if (raw.startsWith('#') && raw.includes('?')) {{
      const [id, qs] = raw.slice(1).split('?');
      const el = document.getElementById(id);
      if (el && el._dfApplyQuery) el._dfApplyQuery(new URLSearchParams(qs));
    }}
  }}
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}})();
</script>
"""

_TONE_NORM = {
    'silver': 'source', 'source': 'source', 'raw': 'source', 'muted': 'source',
    'gold': 'calc', 'calc': 'calc', 'accent': 'calc', 'mart': 'calc',
    'infer': 'llm', 'llm': 'llm', 'ai': 'llm', 'warn': 'llm',
    'pub': 'pub', 'publish': 'pub', 'output': 'pub', 'screen': 'pub', 'ok': 'pub',
    'ops': 'ops',
}
_ST_LABEL = {'ok': '실측', 'has': '있음', 'plan': '계획', 'todo': '만들 것', 'gap': '미구현'}


def _norm_col(c):
    k = c.get('k', c.get('kind', '키' if c.get('key') else ''))
    return {
        'c': str(c.get('c', c.get('name', ''))),
        't': str(c.get('t', c.get('type', ''))),
        'k': str(k),
        'm': str(c.get('m', c.get('mean', ''))),
        'ly': str(c.get('ly', c.get('tone', ''))),
        's': [list(p) for p in c.get('s', c.get('src', []))],
        'g': list(c.get('g', c.get('cfg', []))),
        'lg': str(c.get('lg', c.get('logic', ''))),
        'cf': str(c.get('cf', c.get('confidence', ''))),
        'nd': bool(c.get('nd', c.get('tentative', False))),
    }


def _normalize_lineage(data):
    raw_lanes = data.get('lanes') or []
    assert raw_lanes, 'lineage: lanes(최소 2개 이상의 의미 레인)가 필요합니다'
    lanes = []
    for ln in raw_lanes:
        if isinstance(ln, (tuple, list)):
            lanes.append({'title': str(ln[0]), 'sub': str(ln[1]) if len(ln) > 1 else '', 'ids': []})
        elif isinstance(ln, dict):
            lanes.append({'title': str(ln['title']), 'sub': str(ln.get('sub', '')), 'ids': list(ln.get('ids', []))})
        else:
            lanes.append({'title': str(ln), 'sub': '', 'ids': []})

    nodes = []
    seen_ids = set()
    for raw in data.get('nodes') or []:
        nid = str(raw['id'])
        assert nid not in seen_ids, f'lineage: 중복 node id: {nid}'
        seen_ids.add(nid)
        li = int(raw.get('lane', 0))
        assert 0 <= li < len(lanes), f'lineage: {nid}의 lane={li}이 lanes 범위(0..{len(lanes) - 1}) 밖입니다'
        if nid not in lanes[li]['ids']:
            lanes[li]['ids'].append(nid)
        raw_layer = str(raw.get('tone', raw.get('layer', 'source' if li == 0 else 'calc')))
        tone = _TONE_NORM.get(raw_layer, 'calc')
        st = str(raw.get('status', raw.get('st', '')))
        cols = [_norm_col(c) for c in (raw.get('cols') or [])]
        extra = [_norm_col(c) for c in (raw.get('extra') or [])]
        always = raw.get('always_open', raw.get('always'))
        if always is None:
            always = (tone == 'llm' and 0 < len(cols) <= 8)
        nodes.append({
            'id': nid,
            'name': str(raw.get('name', nid)),
            'lane': li,
            'tone': tone,
            'layerLabel': str(raw.get('layerLabel', raw.get('layer_label', lanes[li]['title']))),
            'group': str(raw.get('group', '')),
            'grain': str(raw.get('grain', '')),
            'kind': str(raw.get('kind', '')),
            'flow': str(raw.get('flow', raw.get('trigger', raw.get('cadence', '')))),
            'trigger': str(raw.get('trigger', '')),
            'key': str(raw.get('key', '')),
            'llm': str(raw.get('llm', '')),
            'edate': str(raw.get('edate', '')),
            'how': str(raw.get('how', '')),
            'cadence': str(raw.get('cadence', '')),
            'st': st,
            'stLabel': str(raw.get('stLabel', raw.get('status_label', _ST_LABEL.get(st, st)))),
            'stText': str(raw.get('stText', raw.get('status_text', ''))),
            'bain': str(raw.get('bain', raw.get('ref', ''))),
            'proposed': bool(raw.get('proposed', False)),
            'wait': list(raw.get('wait') or []),
            'tags': list(raw.get('tags') or []),
            'total': raw.get('total'),
            'always': bool(always),
            'meta': [list( pair ) for pair in (raw.get('meta') or [])],
            'cols': cols,
            'extra': extra,
        })

    edges = []
    edge_set = set()
    for a, b in (data.get('edges') or []):
        assert a in seen_ids and b in seen_ids, f'lineage: 존재하지 않는 노드를 잇는 간선: {a!r} -> {b!r}'
        if (a, b) not in edge_set and a != b:
            edges.append([a, b])
            edge_set.add((a, b))
    if data.get('infer_edges', True):
        for n in nodes:
            for c in n['cols'] + n['extra']:
                for src_tbl, _ in c['s']:
                    if src_tbl in seen_ids and src_tbl != n['id'] and (src_tbl, n['id']) not in edge_set:
                        edges.append([src_tbl, n['id']])
                        edge_set.add((src_tbl, n['id']))

    out = {
        'lanes': lanes,
        'nodes': nodes,
        'edges': edges,
        'soft': [list(e) for e in (data.get('soft') or [])],
    }
    for opt in ('boxWidth', 'gapX', 'gapY', 'defaultStat', 'allowBack'):
        if opt in data:
            out[opt] = data[opt]
    return out


def lineage(data, caption, fid='fig-erd', label=None, lead=None, default_fit=True, max_height=None, dark=False):
    """수십 개 표와 수백 개 열의 다단 연결도(ERD·리니지)를 점진적 노출 방식으로 생성한다.
    - 기본은 '키만' 접기 + 연한 표 단위 골격선만 노출하고, 클릭 시 상류(초록)·하류(파랑)를 끝까지 추적하며 열 단위 선을 긋는다.
    - 외부 라이브러리·웹폰트 없이 오프라인·폐쇄망에서 그대로 동작한다."""
    norm = _normalize_lineage(data)
    aria = label or f'{norm["lanes"][0]["title"]}부터 {norm["lanes"][-1]["title"]}까지 표 {len(norm["nodes"])}개·연결 {len(norm["edges"])}개의 데이터 연결도'
    tone_labels = []
    seen_tones = set()
    default_tone_names = {'source': '원천 (silver)', 'calc': '계산 (gold)', 'llm': '추론 (LLM)', 'pub': '조립 · 게시', 'ops': '운영'}
    custom_leg = data.get('legend')
    if custom_leg:
        tone_labels = [( _TONE_NORM.get(t, t), txt ) for t, txt in custom_leg]
    else:
        for n in norm['nodes']:
            if n['tone'] not in seen_tones:
                seen_tones.add(n['tone'])
                tone_labels.append((n['tone'], default_tone_names.get(n['tone'], n['layerLabel'])))
    has_dash = any(n['st'] in ('plan', 'todo', 'gap') for n in norm['nodes'])
    has_pending = any(c['cf'] in ('nd', 'no') for n in norm['nodes'] for c in n['cols'] + n['extra'])

    leg_parts = [f'<span><i class="df-sw T-{esc(t)}"></i>{esc(txt)}</span>' for t, txt in tone_labels]
    if has_dash:
        leg_parts.append('<span><i class="df-sw dash"></i>점선 = 아직 없는 표 (계획 · 만들 것)</span>')
    leg_parts.append('<span><i class="df-ln up"></i>읽는 쪽 (상류)</span>')
    leg_parts.append('<span><i class="df-ln dn"></i>읽히는 쪽 (하류)</span>')
    if has_pending:
        leg_parts.append('<span><i class="df-dot"></i>재료 열 미정</span>')

    lead_html = ''
    if lead:
        leads = [lead] if isinstance(lead, str) else list(lead)
        lead_html = ''.join(f'<p class="df-lead">{p}</p>' for p in leads)

    mh = f' style="max-height:{int(max_height)}px"' if max_height else ''
    th = ' data-theme="dark"' if dark else ''
    fit_on = ' class="on"' if default_fit else ''
    one_on = '' if default_fit else ' class="on"'
    json_str = json.dumps(norm, ensure_ascii=False).replace('</', '<\\/')

    return (
        f'<figure class="fig fig-lineage" id="{esc(fid)}" data-default-fit="{1 if default_fit else 0}"{th}>\n'
        f'{lead_html}'
        f'<div class="df-bar">'
        f'<span class="df-lb">열</span><span class="df-seg df-mode"><button type="button" data-m="key" class="on">키만</button><button type="button" data-m="all">전부</button></span>'
        f'<span class="df-lb">크기</span><span class="df-seg df-zoom"><button type="button" data-z="one"{one_on}>원래 크기</button><button type="button" data-z="fit"{fit_on}>한눈에</button></span>'
        f'<span class="df-src-wrap"><span class="df-lb" style="margin-right:8px">원천이 들어오면</span><span class="df-seg df-src"></span></span>'
        f'</div>\n'
        f'<div class="df-leg">{"".join(leg_parts)}</div>\n'
        f'<div class="df-stat" aria-live="polite"></div>\n'
        f'<div class="df-scroll"{mh}><div class="df-spacer"><div class="df-canvas"><svg class="df-wires" role="img" aria-label="{esc(aria)}"></svg></div></div></div>\n'
        f'<figcaption>{caption}</figcaption>\n'
        f'<div class="df-panel" role="dialog" aria-label="표·열 상세 정의" hidden></div>\n'
        f'<script type="application/json" class="df-lineage-data">{json_str}</script>\n'
        f'</figure>\n'
    )


def tab_wrap(doc_html, fig_html, doc_label='설계 문서', fig_label='연결도', tab_id='erd'):
    """긴 본문(설계 문서)과 넓은 연결도(lineage)를 탭으로 분리해 본문 읽기 흐름을 해치지 않고 한 파일에 담는다."""
    return (
        f'<div class="df-tabs" role="tablist" data-df-tabs="{esc(tab_id)}">'
        f'<button type="button" role="tab" data-tab="doc" aria-selected="true">{esc(doc_label)}</button>'
        f'<button type="button" role="tab" data-tab="{esc(tab_id)}" aria-selected="false">{esc(fig_label)}</button>'
        f'</div>\n'
        f'<div id="tab-doc" data-tab-panel="doc">\n{doc_html}\n</div>\n'
        f'<div id="{esc(tab_id)}" data-tab-panel="{esc(tab_id)}" class="df-wide" hidden>\n{fig_html}\n</div>\n'
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

    def _ensure_lineage_assets(self):
        if 'fig-lineage' not in self.html and 'data-df-tabs=' not in self.html:
            return
        if LINEAGE_MARK not in self.html:
            i = self.html.index('</style>')
            self.html = self.html[:i] + LINEAGE_CSS + self.html[i:]
        if f'id="{LINEAGE_SCRIPT_ID}"' not in self.html:
            if '</body>' in self.html:
                i = self.html.rindex('</body>')
                self.html = self.html[:i] + LINEAGE_JS + self.html[i:]
            else:
                self.html += '\n' + LINEAGE_JS

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
        self._ensure_lineage_assets()
        out = self.html.replace('\n', '\r\n') if self.crlf else self.html
        io.open(self.path, 'w', encoding='utf-8', newline='').write(out)


# ---------------------------------------------------------------- 점검·스크린샷
def check(path):
    s = io.open(path, encoding='utf-8').read()
    probs = []
    # 스크립트 블록 밖의 실제 DOM SVG만 검사
    dom = re.sub(r'<script\b.*?</script>', '', s, flags=re.S)
    for m in re.finditer(r'<svg\b.*?</svg>', dom, re.S):
        body = m.group(0)
        if re.search(r'<script|<foreignObject|<image|href="http', body):
            probs.append('svg 안에 script·foreignObject·image·외부 링크')
        if 'aria-label=' not in body[:400] and 'aria-hidden="true"' not in body[:400]:
            probs.append('svg에 aria-label 없음')
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
    # lineage JSON 정합성·가독성 규칙 점검 (레인 수, 역방향 간선, 참조 무결성)
    for jm in re.finditer(r'<script type="application/json" class="df-lineage-data">(.*?)</script>', s, re.S):
        try:
            g = json.loads(jm.group(1))
        except Exception as e:
            probs.append(f'lineage JSON 파싱 오류: {e}')
            continue
        lanes = g.get('lanes') or []
        if len(lanes) > 8:
            probs.append(f'lineage 레인 과다({len(lanes)}개) — 번호 나열 대신 의미·계기 기준으로 4~7개 이내로 묶으세요')
        nmap = {n['id']: n for n in (g.get('nodes') or [])}
        cmap = {(n['id'], c['c']) for n in nmap.values() for c in (n.get('cols') or []) + (n.get('extra') or [])}
        back = []
        for a, b in (g.get('edges') or []):
            if a not in nmap or b not in nmap:
                probs.append(f'lineage 없는 노드 참조 간선: {a} -> {b}')
            elif nmap[a].get('lane', 0) > nmap[b].get('lane', 0) and not g.get('allowBack'):
                back.append(f'{a}->{b}')
        if back:
            probs.append(f'lineage 역방향(오른쪽→왼쪽) 간선 {len(back)}개({", ".join(back[:4])}) — 상류→하류 단방향으로 레인을 배치하세요')
        bad_cols = []
        for n in nmap.values():
            for c in (n.get('cols') or []) + (n.get('extra') or []):
                for st, sc in (c.get('s') or []):
                    if (st, sc) not in cmap:
                        bad_cols.append(f'{n["id"]}.{c["c"]}<-{st}.{sc}')
        if bad_cols:
            probs.append(f'lineage 없는 원천 열 참조 {len(bad_cols)}건({", ".join(bad_cols[:3])})')
    if ('fig-lineage' in dom or 'data-df-tabs=' in dom) and f'id="{LINEAGE_SCRIPT_ID}"' not in s:
        probs.append('lineage 스크립트 누락 (Doc.save()로 저장하세요)')
    base = os.path.dirname(path) or '.'
    for h in re.findall(r'href="([^"#]+)', dom):
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', h):   # https:, mailto: 등 외부 링크는 건너뜀
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
    """그림마다 밝은·어두운 화면 PNG. 문서의 <style>(및 lineage 런타임)을 함께 넣어 실제 모양 그대로 찍는다."""
    s = io.open(path, encoding='utf-8').read()
    style = ''.join(re.findall(r'<style>.*?</style>', s, re.S))
    ljs_m = re.search(rf'<script id="{LINEAGE_SCRIPT_ID}">.*?</script>', s, re.S)
    ljs = ljs_m.group(0) if ljs_m else ''
    figs = re.findall(r'<figure class="fig(?:\s+[^"]*)?"[^>]*>.*?</figure>', s, re.S)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    chrome = _chrome()
    profile_dir = _headless_profile_dir()
    outs = []
    for i, f in enumerate(figs, 1):
        is_lin = 'df-lineage-data' in f
        if is_lin:
            f_render = re.sub(r'data-default-fit="[01]"', 'data-default-fit="1"', f, count=1)
            w, h, extra_js = 1440, 1100, ljs
            extra_flags = ['--virtual-time-budget=1200']
        else:
            f_render = f
            vb = re.search(r'<svg viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', f)
            w = 1100
            h = int(float(vb.group(2))) + 260 if vb else 900
            extra_js = ''
            extra_flags = []
        for theme in ('light', 'dark'):
            attr = ' data-theme="dark"' if theme == 'dark' else ' data-theme="light"'
            bg = DARK['panel'] if theme == 'dark' else LIGHT['panel']
            page = (f'<!doctype html><html{attr}><head><meta charset="utf-8">{style}</head>'
                    f'<body style="margin:0;padding:16px;width:{w - 40}px;background:{bg}"><main>{f_render}</main>{extra_js}</body></html>')
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
