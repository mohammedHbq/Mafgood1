from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import and_, or_
from extensions import db
from models.user import User
from models.item import Item, ItemStatus
from models.message import Message
from models.report import Report, Notification

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('هذه الصفحة للمسؤولين فقط', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────── Dashboard ───────────────────────────────────────

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'total_users':     User.query.count(),
        'active_users':    User.query.filter_by(profile_status='active').count(),
        'suspended_users': User.query.filter_by(profile_status='suspended').count(),
        'blocked_users':   User.query.filter_by(profile_status='blocked').count(),
        'total_items':     Item.query.count(),
        'not_found_items': Item.query.filter_by(status=ItemStatus.NOT_FOUND).count(),
        'found_items':     Item.query.filter_by(status=ItemStatus.FOUND_OWNER).count(),
        'pending_reports': Report.query.filter_by(status='pending').count(),
        'total_messages':  Message.query.count(),
    }
    recent_users   = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_reports = Report.query.filter_by(status='pending')\
                                 .order_by(Report.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html', stats=stats,
                           recent_users=recent_users, reports=recent_reports)


# ─────────────────────────── Users ───────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    search = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    query  = User.query
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.full_name.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%'))
        )
    if status:
        query = query.filter_by(profile_status=status)
    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, search=search, status_filter=status)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_profile(user_id):
    """عرض بروفايل المستخدم الكامل مع كل أغراضه."""
    user  = User.query.get_or_404(user_id)
    items = Item.query.filter_by(user_id=user_id).order_by(Item.created_at.desc()).all()
    return render_template('admin/user_profile.html', user=user, items=items,
                           all_statuses=list(ItemStatus))


@admin_bp.route('/users/<int:user_id>/block', methods=['POST'])
@login_required
@admin_required
def block_profile(user_id):
    user = User.query.get_or_404(user_id)
    user.profile_status = 'blocked'
    Notification.send(user.id, 'تم حظر حسابك من قِبل المسؤول. تواصل معنا لمزيد من التفاصيل.')
    db.session.commit()
    flash(f'تم حظر المستخدم {user.username}', 'warning')
    return redirect(request.referrer or url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@login_required
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    phone_number = request.form.get('phone_number', '').strip()
    university_email = request.form.get('university_email', '').strip()

    if not full_name or not email:
        flash('يرجى إدخال الاسم والبريد الإلكتروني', 'danger')
        return redirect(url_for('admin.user_profile', user_id=user_id))

    existing = User.query.filter(User.email == email, User.id != user.id).first()
    if existing:
        flash('هذا البريد الإلكتروني مستخدم بالفعل', 'danger')
        return redirect(url_for('admin.user_profile', user_id=user_id))

    user.full_name = full_name
    user.email = email
    user.phone_number = phone_number or None
    user.university_email = university_email or None
    try:
        db.session.commit()
        flash('تم تحديث بيانات المستخدم', 'success')
    except Exception:
        db.session.rollback()
        flash('حدث خطأ أثناء تحديث بيانات المستخدم', 'danger')

    return redirect(url_for('admin.user_profile', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_account(user_id):
    user = User.query.get_or_404(user_id)
    user.profile_status = 'suspended'
    Notification.send(user.id, 'تم تعليق حسابك مؤقتاً. تواصل مع المسؤول لإعادة التفعيل.')
    db.session.commit()
    flash(f'تم تعليق حساب {user.username}', 'warning')
    return redirect(request.referrer or url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/activate', methods=['POST'])
@login_required
@admin_required
def activate_account(user_id):
    user = User.query.get_or_404(user_id)
    user.profile_status = 'active'
    Notification.send(user.id, 'تم تفعيل حسابك بنجاح. يمكنك الدخول والاستخدام الآن.')
    db.session.commit()
    flash(f'تم تفعيل حساب {user.username}', 'success')
    return redirect(request.referrer or url_for('admin.manage_users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_account(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('تم حذف الحساب', 'info')
    return redirect(url_for('admin.manage_users'))


# ────────────────────────── Items (Admin) ────────────────────────────────────

@admin_bp.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(item_id):
    item = Item.query.get_or_404(item_id)
    owner_id  = item.user_id
    item_name = item.item_name
    deleted = item.delete_item()
    if not deleted:
        flash('لم يتم حذف المنشور. حاول مجدداً أو تواصل مع الدعم.', 'danger')
        return redirect(request.referrer or url_for('admin.dashboard'))

    Notification.send(owner_id, f'قام المسؤول بحذف غرضك "{item_name}".')
    db.session.commit()
    flash('تم حذف المنشور وإشعار صاحبه', 'info')
    return redirect(request.referrer or url_for('admin.dashboard'))


@admin_bp.route('/items/<int:item_id>/update-status', methods=['POST'])
@login_required
@admin_required
def admin_update_item_status(item_id):
    item = Item.query.get_or_404(item_id)
    new_status_val = request.form.get('status', '')
    try:
        item.status = ItemStatus(new_status_val)
        Notification.send(item.user_id,
                          f'قام المسؤول بتحديث حالة غرضك "{item.item_name}" إلى: {item.status.value}')
        db.session.commit()
        flash(f'تم تغيير حالة الغرض إلى: {item.status.value}', 'success')
    except ValueError:
        flash('حالة غير صحيحة', 'danger')
    return redirect(request.referrer or url_for('admin.dashboard'))


# ─────────────────────────── Reports ─────────────────────────────────────────

@admin_bp.route('/messages')
@login_required
@admin_required
def manage_messages():
    item_id = request.args.get('item_id', '').strip()
    user_id = request.args.get('user_id', '').strip()
    query = Message.query
    if item_id.isdigit():
        query = query.filter_by(item_id=int(item_id))
    if user_id.isdigit():
        query = query.filter(
            (Message.sender_id == int(user_id)) | (Message.receiver_id == int(user_id))
        )
    messages = query.order_by(Message.created_at.desc()).all()
    return render_template('admin/messages.html', messages=messages,
                           item_id=item_id, user_id=user_id)


@admin_bp.route('/messages/<int:message_id>/thread')
@login_required
@admin_required
def message_thread(message_id):
    message = Message.query.get_or_404(message_id)
    item = message.item
    partner = message.receiver if message.sender_id == item.user_id else message.sender

    conversation = Message.query.filter(
        Message.item_id == item.id,
        or_(
            and_(Message.sender_id == message.sender_id, Message.receiver_id == message.receiver_id),
            and_(Message.sender_id == message.receiver_id, Message.receiver_id == message.sender_id)
        )
    ).order_by(Message.created_at.asc()).all()

    return render_template('admin/message_thread.html', item=item,
                           partner=partner,
                           messages=conversation,
                           return_url=url_for('admin.manage_messages'))


@admin_bp.route('/messages/<int:message_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    db.session.delete(message)
    db.session.commit()
    flash('تم حذف الرسالة بنجاح', 'info')
    return redirect(request.referrer or url_for('admin.manage_messages'))


@admin_bp.route('/reports')
@login_required
@admin_required
def view_reports():
    status_filter = request.args.get('status', '')
    query = Report.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    reports = query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports, status_filter=status_filter)


@admin_bp.route('/reports/<int:report_id>/update', methods=['POST'])
@login_required
@admin_required
def update_report_status(report_id):
    report     = Report.query.get_or_404(report_id)
    new_status = request.form.get('status', 'actioned')
    report.status = new_status

    # تنبيه صاحب الغرض المُبلَّغ عنه
    label = 'تم اتخاذ الإجراء' if new_status == 'actioned' else 'تم رفض البلاغ'
    if report.item:
        Notification.send(
            report.item.user_id,
            f'البلاغ المقدم ضد غرضك "{report.item.item_name}" تم معالجته: {label}.'
        )
    # تنبيه المُبلِّغ أيضاً
    Notification.send(
        report.reporter_id,
        f'بلاغك عن الغرض "{report.item.item_name if report.item else report.item_id}" تم معالجته: {label}.'
    )
    db.session.commit()
    flash(f'تم تحديث حالة البلاغ إلى: {label}', 'success')
    return redirect(url_for('admin.view_reports'))


# ─────────────────────────── Notifications (mark read) ───────────────────────

@admin_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False)\
                      .update({'is_read': True})
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))
