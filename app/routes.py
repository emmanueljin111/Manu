from flask import (Blueprint, flash, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash

from .db import get_db
from .services import (create_event, create_plan, delete_plan, export_plan_pdf,
                       export_plan_pptx, fetch_calendar_events, fetch_plan,
                       fetch_plan_for_share, fetch_plans, fetch_song_library,
                       fetch_song_options, fetch_users_by_role,
                       save_plan_roles)


bp = Blueprint('main', __name__)


PUBLIC_ROUTES = {'main.login', 'main.share_plan', 'static'}


def register(app):
    app.register_blueprint(bp)

    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ROUTES or request.endpoint is None:
            return
        if session.get('user_id') is None:
            return redirect(url_for('main.login'))

    @app.context_processor
    def inject_globals():
        return {'current_user': get_current_user()}


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            flash('Bienvenue, {}!'.format(user['display_name']), 'success')
            return redirect(url_for('main.dashboard'))
        flash('Identifiants invalides.', 'danger')
    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Vous êtes déconnecté.', 'info')
    return redirect(url_for('main.login'))


@bp.route('/')
def dashboard():
    db = get_db()
    upcoming_plans = fetch_plans(limit=5)
    events = fetch_calendar_events(limit=6)
    song_stats = db.execute('SELECT theme, COUNT(*) as count FROM songs GROUP BY theme').fetchall()
    return render_template('dashboard.html', upcoming_plans=upcoming_plans, events=events, song_stats=song_stats)


@bp.route('/songs')
def songs():
    query = request.args.get('q', '')
    theme = request.args.get('theme', '')
    songs = fetch_song_library(query=query, theme=theme)
    themes = [row['theme'] for row in get_db().execute('SELECT DISTINCT theme FROM songs ORDER BY theme').fetchall() if row['theme']]
    return render_template('songs/list.html', songs=songs, query=query, selected_theme=theme, themes=themes)


@bp.route('/songs/new', methods=['GET', 'POST'])
def new_song():
    if request.method == 'POST':
        form = request.form
        db = get_db()
        db.execute(
            'INSERT INTO songs (title, author, theme, pdf_url, ppt_url, chords_url, tags) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                form['title'],
                form.get('author'),
                form.get('theme'),
                form.get('pdf_url'),
                form.get('ppt_url'),
                form.get('chords_url'),
                form.get('tags')
            )
        )
        db.commit()
        flash('Chant ajouté avec succès.', 'success')
        return redirect(url_for('main.songs'))
    return render_template('songs/form.html', song=None)


@bp.route('/songs/<int:song_id>/edit', methods=['GET', 'POST'])
def edit_song(song_id: int):
    db = get_db()
    song = db.execute('SELECT * FROM songs WHERE id = ?', (song_id,)).fetchone()
    if not song:
        flash('Chant introuvable.', 'danger')
        return redirect(url_for('main.songs'))
    if request.method == 'POST':
        form = request.form
        db.execute(
            'UPDATE songs SET title = ?, author = ?, theme = ?, pdf_url = ?, ppt_url = ?, chords_url = ?, tags = ? WHERE id = ?',
            (
                form['title'],
                form.get('author'),
                form.get('theme'),
                form.get('pdf_url'),
                form.get('ppt_url'),
                form.get('chords_url'),
                form.get('tags'),
                song_id
            )
        )
        db.commit()
        flash('Chant mis à jour.', 'success')
        return redirect(url_for('main.songs'))
    return render_template('songs/form.html', song=song)


@bp.route('/plans')
def plans():
    plans = fetch_plans()
    return render_template('plans/list.html', plans=plans)


@bp.route('/plans/new', methods=['GET', 'POST'])
def new_plan():
    db = get_db()
    songs = fetch_song_options()
    leaders = fetch_users_by_role('responsable')
    musicians = fetch_users_by_role('musicien')
    technicians = fetch_users_by_role('technicien')

    if request.method == 'POST':
        plan_data = {
            'title': request.form['title'],
            'service_date': request.form['service_date'],
            'notes': request.form.get('notes'),
            'leader_id': request.form.get('leader_id') or None,
            'songs': [],
            'roles': []
        }

        for idx, song_id in enumerate(request.form.getlist('song_id')):
            if not song_id:
                continue
            plan_data['songs'].append({
                'song_id': int(song_id),
                'order_index': idx,
                'transition_notes': request.form.getlist('transition_notes')[idx],
                'key_signature': request.form.getlist('key_signature')[idx]
            })

        for role_field in ('responsable', 'musicien', 'technicien'):
            for participant in request.form.getlist(f'{role_field}_participants'):
                if participant.strip():
                    plan_data['roles'].append({'role': role_field, 'participant': participant.strip()})

        plan_id = create_plan(plan_data)
        flash('Plan de louange créé.', 'success')
        return redirect(url_for('main.view_plan', plan_id=plan_id))

    return render_template('plans/form.html', songs=songs, leaders=leaders, musicians=musicians, technicians=technicians)


@bp.route('/plans/<int:plan_id>')
def view_plan(plan_id: int):
    plan = fetch_plan(plan_id)
    if not plan:
        flash('Plan introuvable.', 'danger')
        return redirect(url_for('main.plans'))
    return render_template('plans/detail.html', plan=plan)


@bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
def remove_plan(plan_id: int):
    delete_plan(plan_id)
    flash('Plan supprimé.', 'info')
    return redirect(url_for('main.plans'))


@bp.route('/plans/<int:plan_id>/export/pdf')
def export_plan_as_pdf(plan_id: int):
    plan = fetch_plan(plan_id)
    if not plan:
        flash('Plan introuvable.', 'danger')
        return redirect(url_for('main.plans'))
    pdf_path = export_plan_pdf(plan)
    return send_file(pdf_path, mimetype='application/pdf', as_attachment=True, download_name=f"plan_{plan_id}.pdf")


@bp.route('/plans/<int:plan_id>/export/pptx')
def export_plan_as_pptx(plan_id: int):
    plan = fetch_plan(plan_id)
    if not plan:
        flash('Plan introuvable.', 'danger')
        return redirect(url_for('main.plans'))
    pptx_path = export_plan_pptx(plan)
    return send_file(pptx_path, mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                     as_attachment=True, download_name=f"plan_{plan_id}.pptx")


@bp.route('/calendar', methods=['GET', 'POST'])
def calendar():
    if request.method == 'POST':
        create_event({
            'title': request.form['title'],
            'event_date': request.form['event_date'],
            'event_type': request.form['event_type'],
            'notes': request.form.get('notes'),
            'plan_id': request.form.get('plan_id') or None,
        })
        flash('Événement ajouté.', 'success')
        return redirect(url_for('main.calendar'))

    events = fetch_calendar_events()
    plans = fetch_plans()
    return render_template('calendar.html', events=events, plans=plans)


@bp.route('/plans/<int:plan_id>/roles', methods=['POST'])
def update_roles(plan_id: int):
    plan = fetch_plan(plan_id)
    if not plan:
        flash('Plan introuvable.', 'danger')
        return redirect(url_for('main.plans'))
    roles_data = []
    for role_field in ('responsable', 'musicien', 'technicien'):
        for participant in request.form.getlist(f'{role_field}_participants'):
            if participant.strip():
                roles_data.append({'role': role_field, 'participant': participant.strip()})
    save_plan_roles(plan_id, roles_data)
    flash('Équipe mise à jour.', 'success')
    return redirect(url_for('main.view_plan', plan_id=plan_id))


@bp.route('/share/<token>')
def share_plan(token: str):
    plan = fetch_plan_for_share(token)
    if not plan:
        flash('Plan introuvable ou lien expiré.', 'danger')
        return redirect(url_for('main.login'))
    return render_template('plans/share.html', plan=plan)


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return user
