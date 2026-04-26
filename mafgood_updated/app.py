import os
from flask import Flask
from extensions import db, bcrypt, login_manager, oauth
from sqlalchemy import text

from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mafgood-secret-key-2024')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mafgood.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    oauth.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'يرجى تسجيل الدخول للوصول إلى هذه الصفحة'
    login_manager.login_message_category = 'warning'

    # Google OAuth setup
    oauth.register(
        name='google',
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

    from routes.auth import auth_bp
    from routes.items import items_bp
    from routes.profile import profile_bp
    from routes.admin import admin_bp
    from routes.main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(items_bp, url_prefix='/items')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    with app.app_context():
        from models import user, item, report, message  # noqa: F401 — registers models
        db.create_all()
        try:
            db.session.execute(text('ALTER TABLE notifications ADD COLUMN link VARCHAR(500)'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
