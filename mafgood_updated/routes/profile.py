from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from extensions import db
from models.item import Item
from models.message import Message
from models.report import Notification

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/')
@login_required
def my_profile():
    my_items = Item.query.filter_by(user_id=current_user.id)\
                         .order_by(Item.created_at.desc()).all()
    return render_template('profile/profile.html', user=current_user, items=my_items)


@profile_bp.route('/notifications')
@login_required
def notifications():
    from models.report import Notification
    notifications = Notification.query.filter_by(user_id=current_user.id)\
                                .order_by(Notification.created_at.desc()).all()
    return render_template('profile/notifications.html', notifications=notifications)


@profile_bp.route('/messages')
@login_required
def messages():
    threads = {}
    messages = Message.query.filter(
        or_(Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id)
    ).order_by(Message.created_at.desc()).all()

    for message in messages:
        item = message.item
        partner = message.receiver if message.sender_id == current_user.id else message.sender
        thread_key = (item.id, partner.id)
        if thread_key not in threads:
            threads[thread_key] = {
                'item': item,
                'partner': partner,
                'last_message': message,
                'count': 1,
            }
        else:
            threads[thread_key]['count'] += 1

    thread_list = sorted(threads.values(), key=lambda x: x['last_message'].created_at, reverse=True)
    return render_template('profile/messages.html', threads=thread_list)


@profile_bp.route('/messages/<int:item_id>/<int:partner_id>', methods=['GET', 'POST'])
@login_required
def message_thread(item_id, partner_id):
    item = Item.query.get_or_404(item_id)
    from models.user import User
    partner = User.query.get_or_404(partner_id)

    conversation_exists = Message.query.filter(
        Message.item_id == item.id,
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == partner.id),
            and_(Message.sender_id == partner.id, Message.receiver_id == current_user.id)
        )
    ).first()

    if not conversation_exists:
        flash('غير مصرح لك بمشاهدة هذه المحادثة أو لا توجد أي رسائل هنا.', 'danger')
        return redirect(url_for('profile.messages'))

    conversation = Message.query.filter(
        Message.item_id == item.id,
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == partner.id),
            and_(Message.sender_id == partner.id, Message.receiver_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).all()

    if request.method == 'POST':
        body = request.form.get('message', '').strip()
        if not body:
            flash('يرجى كتابة رسالة قبل الإرسال.', 'danger')
            return redirect(url_for('profile.message_thread', item_id=item.id, partner_id=partner.id))

        receiver_id = partner.id
        message = Message(
            item_id=item.id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            body=body,
        )
        db.session.add(message)

        if receiver_id == item.user_id:
            # sender replies to owner, so the owner should open the thread with sender as partner
            message_link = url_for('profile.message_thread', item_id=item.id, partner_id=current_user.id)
        else:
            # owner replies to sender, so the sender should open the thread with owner as partner
            message_link = url_for('profile.message_thread', item_id=item.id, partner_id=item.user_id)

        Notification.send(
            receiver_id,
            f'لديك رسالة جديدة من {current_user.full_name} حول المنتج "{item.item_name}".',
            link=message_link
        )
        db.session.commit()

        flash('تم إرسال الرسالة.', 'success')
        return redirect(url_for('profile.message_thread', item_id=item.id, partner_id=partner.id))

    return render_template('profile/message_thread.html', item=item,
                           partner=partner,
                           messages=conversation)


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        full_name        = request.form.get('full_name', '').strip()
        phone_number     = request.form.get('phone_number', '').strip()
        university_email = request.form.get('university_email', '').strip()

        success = current_user.update_profile_info(
            full_name=full_name,
            phone_number=phone_number or None,
            university_email=university_email or None,
        )
        if success:
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
        else:
            flash('حدث خطأ أثناء التحديث', 'danger')
        return redirect(url_for('profile.my_profile'))

    return render_template('profile/edit.html', user=current_user)


@profile_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password     = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_user.check_password(current_password):
            flash('كلمة المرور الحالية غير صحيحة', 'danger')
            return render_template('profile/change_password.html')

        if new_password != confirm_password:
            flash('كلمتا المرور الجديدتان غير متطابقتين', 'danger')
            return render_template('profile/change_password.html')

        if len(new_password) < 6:
            flash('يجب أن تكون كلمة المرور 6 أحرف على الأقل', 'danger')
            return render_template('profile/change_password.html')

        current_user.reset_password(new_password)
        flash('تم تغيير كلمة المرور بنجاح', 'success')
        return redirect(url_for('profile.my_profile'))

    return render_template('profile/change_password.html')


@profile_bp.route('/user/<int:user_id>')
def view_user_profile(user_id):
    from models.user import User
    user  = User.query.get_or_404(user_id)
    from models.item import ItemStatus
    items = Item.query.filter_by(user_id=user_id, status=ItemStatus.NOT_FOUND)\
                      .order_by(Item.created_at.desc()).all()
    return render_template('profile/view_user.html', user=user, items=items)
