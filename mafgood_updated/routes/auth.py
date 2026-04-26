from flask import Blueprint, render_template, redirect, url_for, flash, request
import os
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, oauth
from models.user import User

auth_bp = Blueprint('auth', __name__)
from authlib.integrations.flask_client import OAuth



@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username         = request.form.get('username', '').strip()
        full_name        = request.form.get('full_name', '').strip()
        email            = request.form.get('email', '').strip()
        university_email = request.form.get('university_email', '').strip()
        phone_number     = request.form.get('phone_number', '').strip()
        password         = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validations
        if not all([username, full_name, email, password, phone_number]):
            flash('يرجى ملء جميع الحقول المطلوبة بما فيها رقم الجوال', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('كلمتا المرور غير متطابقتين', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم مستخدم بالفعل', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مستخدم بالفعل', 'danger')
            return render_template('auth/register.html')

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            university_email=university_email or None,
            phone_number=phone_number,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('تم إنشاء حسابك بنجاح! يمكنك تسجيل الدخول الآن.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.profile_status in ('suspended', 'blocked'):
                flash('حسابك موقوف أو محظور. تواصل مع الإدارة.', 'danger')
                return render_template('auth/login.html')
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'مرحباً {user.full_name}!', 'success')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('main.index'))


# ── Google OAuth ──────────────────────────────────────────────────────────────

@auth_bp.route('/google/login')
def google_login():
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo')

    if not userinfo:
        flash('فشل تسجيل الدخول بقوقل. حاول مرة أخرى.', 'danger')
        return redirect(url_for('auth.login'))

    email     = userinfo.get('email')
    full_name = userinfo.get('name', email)
    # نستخدم الـ sub (Google ID) كـ username فريد
    google_id = userinfo.get('sub')
    username  = f'google_{google_id}'

    # ابحث عن المستخدم أو أنشئه
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            username=username,
            full_name=full_name,
            email=email,
            email_verified=True,
            profile_status='active',
        )
        import secrets
        user.set_password(secrets.token_urlsafe(32))
        db.session.add(user)
        db.session.commit()
        flash(f'مرحباً {full_name}! تم إنشاء حسابك بنجاح.', 'success')
    else:
        flash(f'مرحباً {user.full_name}!', 'success')

    if user.profile_status in ('suspended', 'blocked'):
        flash('حسابك موقوف أو محظور.', 'danger')
        return redirect(url_for('auth.login'))

    login_user(user)
    return redirect(url_for('main.index'))
