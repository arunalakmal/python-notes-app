import os
import functools

from flask import Flask, render_template, redirect, url_for, request, session, flash, g
from flask_migrate import Migrate
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.security import generate_password_hash, check_password_hash

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    API_URL,
    config={  # Swagger UI config overrides
        'app_name': "Test application"
    },
    # oauth_config={  # OAuth config. See https://github.com/swagger-api/swagger-ui#oauth2-configuration .
    #    'clientId': "your-client-id",
    #    'clientSecret': "your-client-secret-if-required",
    #    'realm': "your-realms",
    #    'appName': "your-app-name",
    #    'scopeSeparator': " ",
    #    'additionalQueryStringParams': {'test': "hello"}
    # }
)

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', default='dev')
    )

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config)

    from .models import db, User, Note, user_schema, users_schema

    db.init_app(app)
    migrate = Migrate(app, db)
    app.register_blueprint(swaggerui_blueprint)

    def require_login(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if not g.user:
                return redirect(url_for('log_in'))
            return view(**kwargs)
        return wrapped_view

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.before_request
    def load_user():
        user_id = session.get('user_id')
        if user_id:
            g.user = User.query.get(user_id)
        else:
            g.user = None

    @app.route('/sign_up', methods=('GET', 'POST'))
    def sign_up():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            error = None

            if not username:
                error = 'Username is required.'
            elif not password:
                error = 'Password is required.'
            elif User.query.filter_by(username=username).first():
                error = 'Username is already taken.'

            if error is None:
                user = User(username=username, password=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                flash("Successfully signed up! Please log in.", 'success')
                return redirect(url_for('log_in'))
            flash(error, 'error')
        return render_template('sign_up.html')
    
    @app.route('/log_in', methods=('GET', 'POST'))
    def log_in():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            error = None

            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password, password):
                error = 'Username or password are incorrect'
            if error is None:
                session.clear()
                session['user_id'] = user.id
                return redirect(url_for('note_index'))
            flash(error, category='error')
        return render_template('log_in.html')
    
    @app.route('/')
    def index():
        return render_template('log_in.html')

    @app.route('/log_out', methods=('GET', 'DELETE'))
    def log_out():
        session.clear()
        flash('Successfully logged out.', 'success')
        return redirect(url_for('log_in'))

    @app.route('/notes')
    @require_login
    def note_index():
        return render_template('note_index.html', notes=g.user.notes)

    @app.route('/notes/new', methods=('GET', 'POST'))
    @require_login
    def note_create():
        if request.method == 'POST':
            title = request.form['title']
            body = request.form['body']
            error = None

            if not title:
                error = 'Title is required.'

            if not error:
                note = Note(author=g.user, title=title, body=body)
                db.session.add(note)
                db.session.commit()
                flash(f"Successfully created note: '{title}'", 'success')
                return redirect(url_for('note_index'))
            flash(error, 'error')
        return render_template('note_create.html')

    @app.route('/notes/<note_id>/edit', methods=('GET', 'POST', 'PATCH', 'PUT'))
    @require_login
    def note_update(note_id):
        note = Note.query.filter_by(user_id=g.user.id, id=note_id).first_or_404()
        if request.method in ['POST', 'PATCH', 'PUT']:
            title = request.form['title']
            body = request.form['body']
            error = None

            if not title:
                error = 'Title is required.'
            
            if not error:
                note.title = title
                note.body = body
                db.session.add(note)
                db.session.commit()
                flash(f"Successfully updated note: '{title}'", 'success')
                return redirect(url_for('note_index'))
            flash(error, 'error')
        return render_template('note_update.html', note=note)

    @app.route('/notes/<note_id>/delete', methods=('GET', 'DELETE'))
    @require_login
    def note_delete(note_id):
        note = Note.query.filter_by(user_id=g.user.id, id=note_id).first_or_404()
        db.session.delete(note)
        db.session.commit()
        flash(f"Successfully deleted note: '{note.title}'", 'success')
        return redirect(url_for('note_index'))

    @app.route('/api/users', methods=['GET'])
    def get_users():
        users = User.query.all()
        return users_schema.dump(users)

    @app.route('/api/users/<id>', methods=['GET'])
    def get_user(id):
        user = User.query.get(id)
        return user_schema.dump(user)
    
    @app.route('/api/delete_user/<id>', methods=['DELETE'])
    def delete_user(id):
        user = User.query.get(id)
        db.session.delete(user)
        db.session.commit()
        return user_schema.dump(user)
    
    @app.route('/api/add_user', methods=['POST'])
    def add_user():
        content_type = request.headers.get('Content-Type')
        if (content_type == 'application/json'):
            json = request.json
            if json.__contains__('password') and json.__contains__('username'):
                username = json['username']
                password = json['password']
                error = None

                if User.query.filter_by(username=username).first():
                    error = 'Username is already taken.\n'
                    return error
                if error is None:
                    user = User(username=username, password=generate_password_hash(password))
                    db.session.add(user)
                    db.session.commit()
                    return 'User successfully added\n'
            else:
                return 'no required content\n'
        else:
            return 'Content-Type not supported!\n'
    return app