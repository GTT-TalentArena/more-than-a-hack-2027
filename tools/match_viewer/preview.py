"""Generate a current-design SVG using invented tracking and labels only."""

import base64
from html import escape
import math
from pathlib import Path

from .estimation import estimated_window
from .server import Session

COLOURS = {'H': '#6b8cff', 'A': '#ff4f8a', 'D': '#777584', 'X': '#92909b'}
FRAMES = [1400, 30, 100, 180, 300, 350, 380, 420, 430, 440, 550, 700, 900, 1050, 1250, 1400]


def main():
    # The synthetic session accepts no match inputs, paths or CSVs.
    session = Session()
    session.load()
    source = session.source
    rows = [estimated_window(source, frame, 1)[0] for frame in FRAMES]
    contexts = [session.label_context(frame) for frame in FRAMES]
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1000" viewBox="0 0 1440 1000" role="img" aria-labelledby="title desc">',
             '<title id="title">GTT local match viewer: current design, synthetic demo</title>',
             '<desc id="desc">Midnight-blue viewer, blue home and pink away players, lime ball and dashed player estimates. Every position and label is invented. Sampled animation, not real-match footage.</desc>']
    css = []
    for family, filename, style in [('Geist', 'geist-latin', 'normal'), ('Geist Mono', 'geist-mono-latin', 'normal'),
                                    ('Bricolage Grotesque', 'bricolage-latin', 'normal'), ('Instrument Serif', 'instrument-serif-italic-latin', 'italic')]:
        font = Path(__file__).with_name('static') / 'fonts' / (filename + '.woff2')
        data = base64.b64encode(font.read_bytes()).decode('ascii')
        css.append('@font-face{font-family:"%s";font-style:%s;font-weight:100 900;src:url(data:font/woff2;base64,%s) format("woff2")}' % (family, style, data))
    css.append('text{font-family:Geist,Arial,sans-serif;fill:#f3eee6}.mono{font-family:"Geist Mono",monospace}.muted{fill:#92909b}.heading{font-family:"Bricolage Grotesque",sans-serif;font-weight:700}.serif{font-family:"Instrument Serif",Georgia,serif;font-style:italic}')
    parts.append('<style>' + ''.join(css) + '</style>')

    def rect(x, y, w, h, fill, radius=0, stroke=None):
        parts.append('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s/>' %
                     (x, y, w, h, radius, fill, '' if stroke is None else ' stroke="%s"' % stroke))

    def text(x, y, value, size=12, cls='', fill=None, anchor='start'):
        parts.append('<text x="%s" y="%s" font-size="%s" class="%s" text-anchor="%s"%s>%s</text>' %
                     (x, y, size, cls, anchor, '' if fill is None else ' style="fill:%s"' % fill, escape(str(value))))

    def animation(attribute, values):
        return '<animate attributeName="%s" values="%s" dur="24s" repeatCount="indefinite" calcMode="discrete"/>' % (attribute, ';'.join(map(str, values)))

    def states(values, draw):
        for value in dict.fromkeys(values):
            parts.append('<g opacity="%s">%s' % (int(value == values[0]), animation('opacity', [int(item == value) for item in values])))
            draw(value)
            parts.append('</g>')

    rect(0, 0, 1440, 1000, '#0b0e2c')
    rect(0, 0, 1440, 63, '#f3eee6')
    rect(0, 62, 1440, 2, '#a50044')
    text(40, 45, 'gtt', 40, 'serif', '#0b0e2c')
    parts.append('<circle cx="87" cy="40" r="4" fill="#ff4f8a"/>')
    rect(570, 17, 277, 32, 'none', 16, '#cccad0')
    rect(574, 20, 119, 26, '#0b0e2c', 13)
    text(633, 38, 'Match viewer', 11, anchor='middle')
    text(771, 38, 'TalentArena · 2027', 10, fill='#5f6178', anchor='middle')
    text(1400, 37, 'LOCAL SESSION', 9, 'mono', '#0b0e2c', 'end')
    text(40, 95, '01 — LOCAL MATCH VIEWER', 10, 'mono muted')
    text(1400, 95, 'SYNTHETIC DEMO / NO MATCH DATA', 9, 'mono muted', anchor='end')
    text(40, 165, 'Who has', 49, 'heading')
    text(40, 217, 'the ball?', 58, 'serif')
    for y, value in [(275, 'Tracking, ball and model'), (309, 'possession. The same match, the'), (343, 'same frame.')]:
        text(40, y, value, 22)
    text(40, 384, 'An invented match to explore the viewer.', 13, 'muted')
    text(40, 407, 'No real match data is included.', 13, 'muted')
    rect(40, 438, 350, 1, '#38394e')
    labels = {'H': 'Home in possession', 'A': 'Away in possession', 'D': 'Dead ball', 'X': 'No answer'}
    for index, label in enumerate('HADX'):
        y = 464 + index * 31
        rect(40, y, 25, 24, COLOURS[label] if label != 'X' else 'none', 6, COLOURS[label])
        text(52.5, y + 16, label, 12, 'mono', '#0b0e2c' if label != 'X' else '#f3eee6', 'middle')
        text(77, y + 17, labels[label], 12)
    for x, y, heading in [(40, 606, 'Frame'), (223, 606, 'Video time'), (40, 665, 'Observed tracks'), (223, 665, 'Estimated tracks'), (40, 725, 'Ball')]:
        rect(x, y, 167, 1, '#38394e')
        text(x, y + 23, heading, 10, 'muted')
    states([f'{frame:,}' for frame in FRAMES], lambda value: text(40, 650, value, 13, 'mono'))
    states([f'{frame // 1500:02d}:{frame // 25 % 60:02d}.{frame % 25 * 4:02d}' for frame in FRAMES], lambda value: text(223, 650, value, 13, 'mono'))
    states([f"{sum(point is not None for point in row['players'])} / 22" for row in rows], lambda value: text(40, 710, value, 13, 'mono'))
    states([sum(point is not None for point in row['player_estimates']) for row in rows], lambda value: text(223, 710, value, 13, 'mono'))
    states(['Observed' if row['ball'] else 'No observation' for row in rows], lambda value: text(40, 770, value, 13))
    rect(43, 790, 15, 15, '#6b8cff', 2)
    text(45, 803, '✓', 12, fill='#0b0e2c')
    text(72, 803, 'Estimate short player gaps', 13)
    for y, value in [(834, '◌  Dashed rings = estimated players'), (854, 'Short gaps ≤ 2 s · long losses fade in 0.6 s'), (874, 'Ball: original observations only.'), (894, 'Track slots are not player identities.')]:
        text(40, y, value, 10, 'muted')
    rect(426, 118, 974, 830, '#12152f', 17, '#38394e')
    text(447, 152, 'FRAME', 10, 'mono')
    states([str(frame).zfill(6) for frame in FRAMES], lambda value: text(485, 152, value, 10, 'mono'))
    text(533, 152, '· 25 FPS', 10, 'mono muted')
    rect(1181, 137, 160, 24, 'none', 12, '#38394e')
    for label in 'HADX':
        parts.append('<g opacity="%s">%s' % (int(source.label(FRAMES[0]) == label), animation('opacity', [int(source.label(frame) == label) for frame in FRAMES])))
        rect(1190, 145, 7, 7, COLOURS[label], 1)
        text(1203, 152, label + ' — ' + labels[label].upper(), 7.5, 'mono')
        parts.append('</g>')
    parts.append('<circle cx="1365" cy="149" r="14" fill="none" stroke="#38394e"/><path d="M1362 144v10m5-10v10" stroke="#92909b" stroke-width="2"/>')
    length, width = source.pitch
    left, top, scale = 537, 196, 752 / length

    def point(xy):
        return round(left + xy[0] * scale, 2), round(top + xy[1] * scale, 2)

    for stripe in range(14):
        rect(left + stripe * length * scale / 14, top, length * scale / 14, width * scale, '#191c38' if stripe % 2 == 0 else '#12152f')
    parts.append('<g fill="none" stroke="#f3eee6" stroke-opacity=".26" stroke-width="1.2">')

    def pitch_rect(x, y, w, h):
        px, py = point((x, y))
        rect(px, py, round(w * scale, 2), round(h * scale, 2), 'none', stroke='#f3eee6')

    pitch_rect(0, 0, length, width)
    pitch_rect(length / 2, 0, 0, width)
    cx, cy = point((length / 2, width / 2))
    radius = round(9.15 * scale, 2)
    parts.append('<circle cx="%s" cy="%s" r="%s"/>' % (cx, cy, radius))
    for side in (0, 1):
        pitch_rect(length - 16.5 if side else 0, (width - 40.32) / 2, 16.5, 40.32)
        pitch_rect(length - 5.5 if side else 0, (width - 18.32) / 2, 5.5, 18.32)
        pitch_rect(length if side else -2, (width - 7.32) / 2, 2, 7.32)
        cx, cy = length - 11 if side else 11, width / 2
        angle = math.acos(5.5 / 9.15)
        a0, a1 = (math.pi - angle, math.pi + angle) if side else (-angle, angle)
        x0, y0 = point((cx + 9.15 * math.cos(a0), cy + 9.15 * math.sin(a0)))
        x1, y1 = point((cx + 9.15 * math.cos(a1), cy + 9.15 * math.sin(a1)))
        parts.append('<path d="M%s %sA%s %s 0 0 1 %s %s"/>' % (x0, y0, radius, radius, x1, y1))
    parts.append('</g>')
    for slot in range(22):
        for estimated in (False, True):
            points = [row['player_estimates' if estimated else 'players'][slot] for row in rows]
            opacities = [round(.7 * row['player_estimate_fade'][slot], 3) if estimated and xy is not None else int(xy is not None) for row, xy in zip(rows, points)]
            colour = COLOURS[source.teams[slot]]
            parts.append('<circle r="6.8" fill="%s"%s>' % ('none' if estimated else colour, ' stroke="%s" stroke-width="1.6" stroke-dasharray="2.5 1.6"' % colour if estimated else ''))
            for axis, attribute in enumerate(('cx', 'cy')):
                parts.append(animation(attribute, [point(xy or (0, 0))[axis] for xy in points]))
            parts.append(animation('opacity', opacities) + '</circle>')
    parts.append('<circle r="4.4" fill="#e8ff2e">')
    for axis, attribute in enumerate(('cx', 'cy')):
        parts.append(animation(attribute, [point(row['ball'] or (0, 0))[axis] for row in rows]))
    parts.append(animation('opacity', [int(row['ball'] is not None) for row in rows]) + '</circle>')
    parts.append('<g opacity="0">' + animation('opacity', [int(row['ball'] is None) for row in rows]))
    rect(550, 206, 155, 24, '#0b0e2c', 12)
    text(562, 222, 'BALL NOT TRACKED', 10, 'mono', '#e8ff2e')
    parts.append('</g>')
    rect(447, 708, 932, 12, '#20233d', 3)
    rect(447, 856, 932, 7, '#20233d', 3)
    for index, context in enumerate(contexts):
        parts.append('<g opacity="%s">%s' % (int(index == 0), animation('opacity', [int(item == index) for item in range(len(rows))])))
        offset = 1000 - (context['end_frame'] - context['start_frame'])
        for spell in context['spells']:
            x = 447 + (offset + spell['start_frame'] - context['start_frame']) / 1000 * 932
            rect(round(x, 2), 708, round((spell['end_frame'] - spell['start_frame']) / 1000 * 932, 2), 12, COLOURS[spell['label']])
        home = context['home_percent']
        text(447, 770, 'HOME ' + ('—' if home is None else str(home) + '%'), 9, 'mono')
        text(904, 770, ('—' if home is None else str(100 - home) + '%') + ' AWAY', 9, 'mono', anchor='end')
        if home is not None:
            rect(447, 780, 457, 6, '#ff4f8a', 3)
            rect(447, 780, 457 * home / 100, 6, '#6b8cff', 3)
        for order, spell in enumerate(context['spells'][-3:][::-1]):
            y = 767 + order * 18
            rect(926, y - 7, 7, 7, COLOURS[spell['label']], 1)
            text(944, y, spell['label'], 9, 'mono')
            text(970, y, '%06d→%06d' % (spell['start_frame'], spell['end_frame'] - 1), 9, 'mono muted')
            text(1379, y, '%.1fs' % ((spell['end_frame'] - spell['start_frame']) / source.fps), 9, 'mono', anchor='end')
        rect(447, 856, round(rows[index]['frame'] / (source.n_frames - 1) * 932, 2), 7, '#6b8cff', 3)
        parts.append('</g>')
    text(447, 733, '−40 S', 8, 'mono muted')
    text(913, 733, 'MODEL LABEL WINDOW', 8, 'mono muted', anchor='middle')
    text(1379, 733, 'NOW', 8, 'mono muted', anchor='end')
    rect(447, 748, 932, 1, '#38394e')
    text(447, 802, 'Window only · H/A labels, excluding D/X', 8, 'muted')
    rect(447, 824, 932, 1, '#38394e')
    text(447, 843, 'TACTICAL VIDEO TIME / FRAME', 8, 'mono muted')
    text(1379, 843, '00:59.96 · 1,500 frames', 8, 'mono muted', anchor='end')
    for x, label in [(447, '←'), (487, '→')]:
        rect(x, 880, 32, 30, 'none', 15, '#38394e')
        text(x + 16, 900, label, 14, anchor='middle')
    text(537, 900, 'Speed', 10, 'muted')
    rect(577, 881, 58, 28, 'none', 14, '#38394e')
    text(606, 900, '1×', 12, anchor='middle')
    text(1205, 900, 'Frame', 10, 'muted')
    rect(1249, 881, 64, 28, 'none', 14, '#38394e')
    states([str(frame) for frame in FRAMES], lambda value: text(1281, 900, value, 11, 'mono', anchor='middle'))
    rect(1323, 881, 56, 28, 'none', 14, '#38394e')
    text(1351, 900, 'Go ↗', 11, anchor='middle')
    for x, team in [(448, 'H'), (499, 'A')]:
        parts.append('<circle cx="%s" cy="929" r="3" fill="%s"/>' % (x, COLOURS[team]))
        text(x + 10, 932, 'Home' if team == 'H' else 'Away', 8, 'muted')
    text(1379, 932, '105.3 × 68 m · 25 fps', 8, 'mono muted', anchor='end')
    text(40, 977, 'Synthetic illustration · invented tracking and labels · sampled animation', 10, 'muted')
    text(1400, 977, 'CSV → POSSESSION   /   ATD → POSITIONS', 9, 'mono muted', anchor='end')
    parts.append('</svg>')
    destination = Path(__file__).resolve().parents[2] / 'docs/assets/match-viewer-synthetic.svg'
    destination.write_text('\n'.join(parts) + '\n', encoding='utf-8')
    print('Updated the current-design synthetic viewer illustration.')


if __name__ == '__main__':
    main()
