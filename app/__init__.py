from flask import Flask

from .db import init_app, ensure_initial_data

def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="change-me",
        DATABASE="instance/louange.sqlite3",
    )

    init_app(app)
    ensure_initial_data(app)

    from . import routes

    routes.register(app)

    return app
