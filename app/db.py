import sqlite3
from pathlib import Path
from datetime import datetime
from flask import current_app, g
from werkzeug.security import generate_password_hash


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('responsable', 'musicien', 'technicien')),
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    theme TEXT,
    pdf_url TEXT,
    ppt_url TEXT,
    chords_url TEXT,
    tags TEXT
);

CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    service_date TEXT NOT NULL,
    notes TEXT,
    leader_id INTEGER,
    created_at TEXT NOT NULL,
    share_token TEXT UNIQUE,
    FOREIGN KEY (leader_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS plan_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    song_id INTEGER NOT NULL,
    order_index INTEGER NOT NULL,
    transition_notes TEXT,
    key_signature TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
    FOREIGN KEY (song_id) REFERENCES songs(id)
);

CREATE TABLE IF NOT EXISTS plan_roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    participant TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    event_date TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('culte', 'repetition')),
    notes TEXT,
    plan_id INTEGER,
    FOREIGN KEY (plan_id) REFERENCES plans(id)
);
"""


def get_db():
    if 'db' not in g:
        db_path = Path(current_app.config['DATABASE'])
        db_path.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)

    @app.cli.command('init-db')
    def init_db_command():
        init_db()
        print('Database initialised.')


def ensure_initial_data(app):
    with app.app_context():
        init_db()
        db = get_db()
        user = db.execute('SELECT id FROM users WHERE username = ?', ('admin',)).fetchone()
        if not user:
            db.execute(
                'INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)',
                ('admin', generate_password_hash('admin123'), 'responsable', 'Admin')
            )
            db.commit()

        if db.execute('SELECT COUNT(*) as c FROM songs').fetchone()['c'] == 0:
            seed_songs = [
                ('Je louerai l’Éternel', 'André Thibault', 'Louange', 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/je-louerai-leternel.pdf',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/je-louerai-leternel.pptx',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/je-louerai-leternel-accords.pdf',
                 'joie;gratitude'),
                ('Dieu est si bon', 'Traditionnel', 'Adoration', 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/dieu-est-si-bon.pdf',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/dieu-est-si-bon.pptx',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/dieu-est-si-bon-accords.pdf',
                 'bonté;confiance'),
                ('Majesté', 'Jack Hayford', 'Adoration', 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/majestes.pdf',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/majestes.pptx',
                 'https://www.epcp-louange.fr/wp-content/uploads/2023/04/majestes-accords.pdf',
                 'adoration;royauté')
            ]
            db.executemany(
                'INSERT INTO songs (title, author, theme, pdf_url, ppt_url, chords_url, tags) VALUES (?, ?, ?, ?, ?, ?, ?)',
                seed_songs
            )
            db.commit()

        if db.execute('SELECT COUNT(*) as c FROM events').fetchone()['c'] == 0:
            now = datetime.now().date()
            events = [
                ('Culte dominical', now.isoformat(), 'culte', 'Culte hebdomadaire', None),
                ('Répétition louange', (now.replace(day=min(now.day + 2, 28))).isoformat(), 'repetition', 'Préparation musicale', None),
            ]
            db.executemany(
                'INSERT INTO events (title, event_date, event_type, notes, plan_id) VALUES (?, ?, ?, ?, ?)',
                events
            )
            db.commit()
