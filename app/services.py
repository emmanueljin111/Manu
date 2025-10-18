import io
import secrets
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .db import get_db


EXPORT_DIR = Path('app/exports')


@dataclass
class SongOption:
    id: int
    title: str
    theme: Optional[str]
    author: Optional[str]


@dataclass
class PlanSong:
    order_index: int
    title: str
    author: Optional[str]
    theme: Optional[str]
    transition_notes: Optional[str]
    key_signature: Optional[str]
    pdf_url: Optional[str]
    ppt_url: Optional[str]
    chords_url: Optional[str]


@dataclass
class Plan:
    id: int
    title: str
    service_date: datetime
    notes: Optional[str]
    leader_name: Optional[str]
    created_at: datetime
    songs: List[PlanSong]
    roles: Dict[str, List[str]]
    share_token: Optional[str]


def fetch_song_library(query: str = '', theme: str = '') -> List[Dict]:
    db = get_db()
    sql = 'SELECT * FROM songs'
    params: List = []
    clauses: List[str] = []
    if query:
        clauses.append('(title LIKE ? OR author LIKE ? OR tags LIKE ?)')
        like = f'%{query}%'
        params.extend([like, like, like])
    if theme:
        clauses.append('theme = ?')
        params.append(theme)
    if clauses:
        sql += ' WHERE ' + ' AND '.join(clauses)
    sql += ' ORDER BY title'
    return db.execute(sql, tuple(params)).fetchall()


def fetch_song_options() -> List[SongOption]:
    db = get_db()
    rows = db.execute('SELECT id, title, theme, author FROM songs ORDER BY title').fetchall()
    return [SongOption(id=row['id'], title=row['title'], theme=row['theme'], author=row['author']) for row in rows]


def fetch_users_by_role(role: str):
    db = get_db()
    return db.execute('SELECT id, display_name FROM users WHERE role = ? ORDER BY display_name', (role,)).fetchall()


def create_plan(data: Dict) -> int:
    db = get_db()
    now = datetime.utcnow().isoformat()
    share_token = secrets.token_urlsafe(16)
    cur = db.execute(
        'INSERT INTO plans (title, service_date, notes, leader_id, created_at, share_token) VALUES (?, ?, ?, ?, ?, ?)',
        (
            data['title'],
            data['service_date'],
            data.get('notes'),
            data.get('leader_id'),
            now,
            share_token
        )
    )
    plan_id = cur.lastrowid
    insert_plan_songs(plan_id, data.get('songs', []))
    save_plan_roles(plan_id, data.get('roles', []), commit=False)
    link_plan_to_event(plan_id, data.get('service_date'))
    db.commit()
    return plan_id


def insert_plan_songs(plan_id: int, songs: Iterable[Dict]):
    db = get_db()
    db.execute('DELETE FROM plan_songs WHERE plan_id = ?', (plan_id,))
    for song in songs:
        db.execute(
            'INSERT INTO plan_songs (plan_id, song_id, order_index, transition_notes, key_signature) VALUES (?, ?, ?, ?, ?)',
            (
                plan_id,
                song['song_id'],
                song['order_index'],
                song.get('transition_notes'),
                song.get('key_signature')
            )
        )


def save_plan_roles(plan_id: int, roles: Iterable[Dict], commit: bool = True):
    db = get_db()
    db.execute('DELETE FROM plan_roles WHERE plan_id = ?', (plan_id,))
    for role in roles:
        db.execute(
            'INSERT INTO plan_roles (plan_id, role, participant) VALUES (?, ?, ?)',
            (
                plan_id,
                role['role'],
                role['participant']
            )
        )
    if commit:
        db.commit()


def fetch_plan(plan_id: int) -> Optional[Plan]:
    db = get_db()
    plan_row = db.execute(
        'SELECT p.*, u.display_name as leader_name FROM plans p LEFT JOIN users u ON p.leader_id = u.id WHERE p.id = ?',
        (plan_id,)
    ).fetchone()
    if not plan_row:
        return None
    return build_plan_from_row(plan_row)


def fetch_plan_for_share(token: str) -> Optional[Plan]:
    db = get_db()
    plan_row = db.execute(
        'SELECT p.*, u.display_name as leader_name FROM plans p LEFT JOIN users u ON p.leader_id = u.id WHERE p.share_token = ?',
        (token,)
    ).fetchone()
    if not plan_row:
        return None
    return build_plan_from_row(plan_row)


def build_plan_from_row(row) -> Plan:
    db = get_db()
    song_rows = db.execute(
        'SELECT ps.order_index, s.*, ps.transition_notes, ps.key_signature FROM plan_songs ps '
        'JOIN songs s ON s.id = ps.song_id WHERE ps.plan_id = ? ORDER BY ps.order_index',
        (row['id'],)
    ).fetchall()
    songs = [
        PlanSong(
            order_index=song_row['order_index'],
            title=song_row['title'],
            author=song_row['author'],
            theme=song_row['theme'],
            transition_notes=song_row['transition_notes'],
            key_signature=song_row['key_signature'],
            pdf_url=song_row['pdf_url'],
            ppt_url=song_row['ppt_url'],
            chords_url=song_row['chords_url'],
        )
        for song_row in song_rows
    ]
    role_rows = db.execute('SELECT role, participant FROM plan_roles WHERE plan_id = ?', (row['id'],)).fetchall()
    roles: Dict[str, List[str]] = {'responsable': [], 'musicien': [], 'technicien': []}
    for role_row in role_rows:
        roles.setdefault(role_row['role'], []).append(role_row['participant'])
    service_date = datetime.fromisoformat(row['service_date']) if row['service_date'] else None
    created_at = datetime.fromisoformat(row['created_at']) if row['created_at'] else None
    return Plan(
        id=row['id'],
        title=row['title'],
        service_date=service_date,
        notes=row['notes'],
        leader_name=row['leader_name'],
        created_at=created_at,
        songs=songs,
        roles=roles,
        share_token=row['share_token']
    )


def fetch_plans(limit: Optional[int] = None):
    db = get_db()
    sql = 'SELECT p.*, u.display_name as leader_name FROM plans p LEFT JOIN users u ON p.leader_id = u.id ORDER BY service_date DESC'
    if limit:
        sql += ' LIMIT ?'
        rows = db.execute(sql, (limit,)).fetchall()
    else:
        rows = db.execute(sql).fetchall()
    return [build_plan_from_row(row) for row in rows]


def delete_plan(plan_id: int):
    db = get_db()
    db.execute('DELETE FROM plans WHERE id = ?', (plan_id,))
    db.commit()


def create_event(data: Dict):
    db = get_db()
    db.execute(
        'INSERT INTO events (title, event_date, event_type, notes, plan_id) VALUES (?, ?, ?, ?, ?)',
        (
            data['title'],
            data['event_date'],
            data['event_type'],
            data.get('notes'),
            data.get('plan_id')
        )
    )
    db.commit()


def fetch_calendar_events(limit: Optional[int] = None):
    db = get_db()
    sql = 'SELECT e.*, p.title as plan_title FROM events e LEFT JOIN plans p ON e.plan_id = p.id ORDER BY event_date'
    params = []
    if limit:
        sql += ' LIMIT ?'
        params.append(limit)
    return db.execute(sql, tuple(params)).fetchall()


def link_plan_to_event(plan_id: int, service_date: Optional[str]):
    if not service_date:
        return
    db = get_db()
    db.execute(
        'UPDATE events SET plan_id = ? WHERE event_date = ? AND event_type = "culte"',
        (plan_id, service_date)
    )


def export_plan_pdf(plan: Plan) -> str:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = EXPORT_DIR / f"plan_{plan.id}.pdf"
    content = build_pdf_bytes(plan)
    with open(filename, 'wb') as f:
        f.write(content)
    return str(filename)


def build_pdf_bytes(plan: Plan) -> bytes:
    # Minimal PDF generator
    lines = [
        f"Plan de louange : {plan.title}",
        f"Date : {plan.service_date.strftime('%d/%m/%Y') if plan.service_date else 'N/A'}",
        f"Responsable : {plan.leader_name or 'N/A'}",
        "",
        "Chants :",
    ]
    for idx, song in enumerate(plan.songs, start=1):
        lines.append(f"{idx}. {song.title} ({song.author or 'Auteur inconnu'})")
        if song.key_signature:
            lines.append(f"   Tonalité : {song.key_signature}")
        if song.transition_notes:
            lines.append(f"   Notes : {song.transition_notes}")
    lines.append("")
    lines.append("Équipe :")
    for role, participants in plan.roles.items():
        label = role.capitalize()
        lines.append(f"{label} : {', '.join(participants) if participants else 'À définir'}")
    if plan.notes:
        lines.append("")
        lines.append("Notes générales :")
        lines.extend(plan.notes.splitlines())

    return create_simple_pdf(lines)


def create_simple_pdf(lines: List[str]) -> bytes:
    # Very small PDF using basic objects
    y = 780
    leading = 18
    content_lines = ["BT", "/F1 12 Tf", "72 {} Td".format(y)]
    for line in lines:
        escaped = escape_pdf_text(line)
        content_lines.append(f"({escaped}) Tj")
        y -= leading
        content_lines.append(f"0 -{leading} Td")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines)
    objects = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
        f"4 0 obj<< /Length {len(content_stream)} >>stream\n{content_stream}\nendstreamendobj".encode('latin-1'),
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
    ]
    offsets = []
    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n")
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj + b"\n")
    xref_pos = pdf.tell()
    pdf.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode('ascii'))
    for offset in offsets:
        pdf.write(f"{offset:010d} 00000 n \n".encode('ascii'))
    pdf.write(b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n")
    pdf.write(str(xref_pos).encode('ascii'))
    pdf.write(b"\n%%EOF")
    return pdf.getvalue()


def escape_pdf_text(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def export_plan_pptx(plan: Plan) -> str:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = EXPORT_DIR / f"plan_{plan.id}.pptx"
    with zipfile.ZipFile(filename, 'w') as pptx:
        add_pptx_core(pptx, plan)
    return str(filename)


def add_pptx_core(zipf: zipfile.ZipFile, plan: Plan):
    slides = plan.songs or [
        PlanSong(
            order_index=0,
            title='Plan de louange',
            author=plan.leader_name,
            theme=plan.service_date.strftime('%d/%m/%Y') if plan.service_date else None,
            transition_notes=plan.notes or 'Aucun chant défini.',
            key_signature=None,
            pdf_url=None,
            ppt_url=None,
            chords_url=None,
        )
    ]
    zipf.writestr('[Content_Types].xml', build_content_types_xml(len(slides)))
    zipf.writestr('_rels/.rels', build_root_rels())
    zipf.writestr('docProps/app.xml', build_app_xml(len(slides)))
    zipf.writestr('docProps/core.xml', build_core_xml(plan))
    zipf.writestr('ppt/presentation.xml', build_presentation_xml(len(slides)))
    zipf.writestr('ppt/_rels/presentation.xml.rels', build_presentation_rels(len(slides)))
    for idx, song in enumerate(slides, start=1):
        zipf.writestr(f'ppt/slides/slide{idx}.xml', build_slide_xml(song, idx))
        zipf.writestr(f'ppt/slides/_rels/slide{idx}.xml.rels', build_slide_rels())
    zipf.writestr('ppt/theme/theme1.xml', build_theme_xml())


def build_content_types_xml(slide_count: int) -> str:
    slides = ''.join([
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    ])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        f'{slides}'
        '</Types>'
    )


def build_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        '</Relationships>'
    )


def build_app_xml(slide_count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Louange Planner</Application>'
        f'<Slides>{max(slide_count, 1)}</Slides>'
        '</Properties>'
    )


def build_core_xml(plan: Plan) -> str:
    created = plan.created_at.isoformat() if plan.created_at else datetime.utcnow().isoformat()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{escape_xml(plan.title)}</dc:title>'
        f'<dc:creator>{escape_xml(plan.leader_name or "Inconnu")}</dc:creator>'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        '</cp:coreProperties>'
    )


def build_presentation_xml(slide_count: int) -> str:
    sld_id_list = ''.join([
        f'<p:sldId id="{256+i}" r:id="rId{i}"/>'
        for i in range(1, slide_count + 1)
    ]) or '<p:sldId id="256" r:id="rId1"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f'<p:sldIdLst>{sld_id_list}</p:sldIdLst>'
        '<p:sldSz cx="12192000" cy="6858000" type="screen4x3"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        '<p:defaultTextStyle/>'
        '</p:presentation>'
    )


def build_presentation_rels(slide_count: int) -> str:
    rels = ''.join([
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    ]) or '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rels}'
        '</Relationships>'
    )


def build_slide_xml(song: PlanSong, idx: int) -> str:
    subtitle_parts = []
    if song.author:
        subtitle_parts.append(song.author)
    if song.key_signature:
        subtitle_parts.append(f"Tonalité : {song.key_signature}")
    if song.theme:
        subtitle_parts.append(f"Thème : {song.theme}")
    subtitle = ' | '.join(subtitle_parts) if subtitle_parts else ''
    body = song.transition_notes or ''
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld>'
        '<p:spTree>'
        '<p:nvGrpSpPr>'
        '<p:cNvPr id="1" name=""/>'
        '<p:cNvGrpSpPr/>'
        '<p:nvPr/>'
        '</p:nvGrpSpPr>'
        '<p:grpSpPr>'
        '<a:xfrm>'
        '<a:off x="0" y="0"/>'
        '<a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/>'
        '<a:chExt cx="0" cy="0"/>'
        '</a:xfrm>'
        '</p:grpSpPr>'
        f'{build_title_shape(song.title)}'
        f'{build_subtitle_shape(subtitle)}'
        f'{build_body_shape(body)}'
        '</p:spTree>'
        '</p:cSld>'
        '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>'
        '</p:sld>'
    )


def build_slide_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )


def build_title_shape(text: str) -> str:
    return (
        '<p:sp>'
        '<p:nvSpPr>'
        '<p:cNvPr id="2" name="Title 1"/>'
        '<p:cNvSpPr/>'
        '<p:nvPr/>'
        '</p:nvSpPr>'
        '<p:spPr>'
        '<a:xfrm>'
        '<a:off x="685800" y="274320"/>'
        '<a:ext cx="10287000" cy="1181100"/>'
        '</a:xfrm>'
        '</p:spPr>'
        f'{build_text_body(text, 40)}'
        '</p:sp>'
    )


def build_subtitle_shape(text: str) -> str:
    return (
        '<p:sp>'
        '<p:nvSpPr>'
        '<p:cNvPr id="3" name="Subtitle 2"/>'
        '<p:cNvSpPr/>'
        '<p:nvPr/>'
        '</p:nvSpPr>'
        '<p:spPr>'
        '<a:xfrm>'
        '<a:off x="685800" y="1524000"/>'
        '<a:ext cx="10287000" cy="914400"/>'
        '</a:xfrm>'
        '</p:spPr>'
        f'{build_text_body(text, 24)}'
        '</p:sp>'
    )


def build_body_shape(text: str) -> str:
    return (
        '<p:sp>'
        '<p:nvSpPr>'
        '<p:cNvPr id="4" name="Body 3"/>'
        '<p:cNvSpPr/>'
        '<p:nvPr/>'
        '</p:nvSpPr>'
        '<p:spPr>'
        '<a:xfrm>'
        '<a:off x="685800" y="2286000"/>'
        '<a:ext cx="10287000" cy="3657600"/>'
        '</a:xfrm>'
        '</p:spPr>'
        f'{build_text_body(text, 20)}'
        '</p:sp>'
    )


def build_text_body(text: str, size: int) -> str:
    text = escape_xml(text)
    return (
        '<p:txBody>'
        '<a:bodyPr/>'
        '<a:lstStyle/>'
        '<a:p>'
        f'<a:pPr><a:defRPr sz="{size*100}"/></a:pPr>'
        f'<a:r><a:rPr lang="fr-FR" sz="{size*100}"/><a:t>{text}</a:t></a:r>'
        '</a:p>'
        '</p:txBody>'
    )


def build_theme_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="LouangeTheme">'
        '<a:themeElements>'
        '<a:clrScheme name="Louange">'
        '<a:dk1><a:srgbClr val="1F1F1F"/></a:dk1>'
        '<a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>'
        '<a:dk2><a:srgbClr val="2F5496"/></a:dk2>'
        '<a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>'
        '<a:accent1><a:srgbClr val="4472C4"/></a:accent1>'
        '<a:accent2><a:srgbClr val="ED7D31"/></a:accent2>'
        '<a:accent3><a:srgbClr val="A5A5A5"/></a:accent3>'
        '<a:accent4><a:srgbClr val="FFC000"/></a:accent4>'
        '<a:accent5><a:srgbClr val="5B9BD5"/></a:accent5>'
        '<a:accent6><a:srgbClr val="70AD47"/></a:accent6>'
        '<a:hlink><a:srgbClr val="0563C1"/></a:hlink>'
        '<a:folHlink><a:srgbClr val="954F72"/></a:folHlink>'
        '</a:clrScheme>'
        '<a:fontScheme name="LouangeFonts">'
        '<a:majorFont>'
        '<a:latin typeface="Calibri"/>'
        '</a:majorFont>'
        '<a:minorFont>'
        '<a:latin typeface="Calibri"/>'
        '</a:minorFont>'
        '</a:fontScheme>'
        '<a:fmtScheme name="LouangeFormats">'
        '<a:fillStyleLst><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:fillStyleLst>'
        '<a:lnStyleLst><a:ln w="9525"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
        '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill></a:bgFillStyleLst>'
        '</a:fmtScheme>'
        '</a:themeElements>'
        '</a:theme>'
    )


def escape_xml(text: str) -> str:
    return (text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace("'", '&apos;'))


def fetch_calendar_for_month(year: int, month: int):
    db = get_db()
    start = datetime(year, month, 1).date()
    end = datetime(year + (1 if month == 12 else 0), (month % 12) + 1, 1).date()
    return db.execute('SELECT * FROM events WHERE event_date >= ? AND event_date < ? ORDER BY event_date', (start.isoformat(), end.isoformat())).fetchall()
