"""Generate the public log illustration from invented observations only."""

from pathlib import Path
from .synthetic import SyntheticTracking


def main():
    source = SyntheticTracking()
    frames = [30, 100, 180, 300, 380, 550, 700, 900, 1050, 1250, 1400, 30]
    rows = [source.window(frame, 1)[0] for frame in frames]
    colours = {"H": "#e9ad64", "A": "#86b9c9", "D": "#e8ece2", "X": "#93a399"}
    names = {"H": "Home possession", "A": "Away possession", "D": "Dead ball", "X": "Model abstention"}
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1120" height="750" viewBox="0 0 1120 750" role="img" aria-labelledby="title desc">',
             '<title id="title">GTT local match viewer: animated synthetic example</title>',
             '<desc id="desc">Invented home and away tracks with H, A, D and X states. Missing observations disappear. No match data is included.</desc>',
             '<style>text{font-family:Arial,Helvetica,sans-serif} .muted{fill:#93a399}</style>',
             '<rect width="1120" height="750" rx="8" fill="#101716"/>',
             '<text x="40" y="53" fill="#e8ece2" font-size="26" font-weight="bold">GTT / MATCH VIEWER</text>',
             '<text x="40" y="83" fill="#e9ad64" font-size="12" letter-spacing="2">SYNTHETIC DEMO · NO MATCH DATA</text>',
             '<text x="40" y="128" fill="#e8ece2" font-size="30">The match, frame by frame.</text>',
             '<rect x="40" y="158" width="810" height="520" fill="#14251c"/>',
             '<g stroke="#a8bda166" stroke-width="1.5" fill="none">',
             '<rect x="85" y="193" width="720" height="465"/><path d="M445 193v465"/>',
             '<circle cx="445" cy="425.5" r="62.6"/>',
             '<path d="M85 287h113v277H85 M805 287H692v277h113 M85 363h38v125H85 M805 363h-38v125h38"/></g>',
             '<text x="878" y="193" class="muted" font-size="11" letter-spacing="2">MODEL OUTPUT</text>']

    def animation(attribute, values):
        return '<animate attributeName="{}" values="{}" dur="18s" repeatCount="indefinite" calcMode="discrete"/>'.format(attribute, ';'.join(str(value) for value in values))

    for slot in range(22):
        points = [row["players"][slot] for row in rows]
        parts.append('<circle r="7" fill="{}" stroke="#101716" stroke-width="2">'.format(colours[source.teams[slot]]))
        parts.append(animation('cx', [round(85 + (point or [0, 0])[0] / source.pitch[0] * 720, 2) for point in points]))
        parts.append(animation('cy', [round(193 + (point or [0, 0])[1] / source.pitch[1] * 465, 2) for point in points]))
        parts.append(animation('opacity', [1 if point else 0 for point in points]))
        parts.append('</circle>')
    points = [row["ball"] for row in rows]
    parts.append('<circle r="5" fill="#fff9e8" stroke="#101716" stroke-width="2">')
    parts.append(animation('cx', [round(85 + (point or [0, 0])[0] / source.pitch[0] * 720, 2) for point in points]))
    parts.append(animation('cy', [round(193 + (point or [0, 0])[1] / source.pitch[1] * 465, 2) for point in points]))
    parts.append(animation('opacity', [1 if point else 0 for point in points]))
    parts.append('</circle>')
    for label in "HADX":
        parts.append('<g opacity="0">' + animation('opacity', [1 if source.label(row['frame']) == label else 0 for row in rows]))
        parts.append('<text x="875" y="290" fill="{}" font-size="88">{}</text>'.format(colours[label], label))
        parts.append('<text x="878" y="325" fill="#e8ece2" font-size="15">{}</text></g>'.format(names[label]))
    parts.extend(['<text x="878" y="390" class="muted" font-size="12">Observations only.</text>',
                  '<text x="878" y="413" class="muted" font-size="12">Gaps stay visible.</text>',
                  '<text x="878" y="436" class="muted" font-size="12">No interpolation.</text>',
                  '<circle cx="50" cy="714" r="4" fill="#e9ad64"/><text x="63" y="718" class="muted" font-size="12">Home</text>',
                  '<circle cx="132" cy="714" r="4" fill="#86b9c9"/><text x="145" y="718" class="muted" font-size="12">Away</text>',
                  '<text x="878" y="620" class="muted" font-size="11">LOCAL TOOL / ISSUE #34</text>',
                  '<text x="878" y="644" class="muted" font-size="11">Invented tracking &amp; labels</text>', '</svg>'])
    destination = Path(__file__).resolve().parents[2] / 'docs' / 'assets' / 'match-viewer-synthetic.svg'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(parts), encoding='utf-8')
    print('Updated the synthetic-only log illustration.')


if __name__ == '__main__':
    main()
