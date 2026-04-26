import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename
from extensions import db
from models.item import Item, ItemCategory, ItemStatus, ItemType, Match
from models.message import Message
from models.report import Report, Notification
from utils.ai_matching import ai_matcher

items_bp = Blueprint('items', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','jfif' 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(file):
    """يحفظ الصورة بـ UUID فريد ويُعيد المسار النسبي."""
    filename  = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)
    return f'uploads/{filename}'


@items_bp.route('/')
def list_items():
    search          = request.args.get('q', '')
    category        = request.args.get('category', '')
    item_type       = request.args.get('type', '')
    selected_status = request.args.get('status', '')

    query = Item.query
    if search:
        query = query.filter(Item.item_name.ilike(f'%{search}%'))
    if category:
        try:
            query = query.filter_by(category=ItemCategory(category))
        except ValueError:
            pass
    if item_type:
        try:
            query = query.filter_by(item_type=ItemType(item_type))
        except ValueError:
            pass
    if selected_status:
        try:
            query = query.filter_by(status=ItemStatus(selected_status))
        except ValueError:
            pass

    items      = query.order_by(Item.created_at.desc()).all()
    categories = [c.value for c in ItemCategory]
    statuses   = list(ItemStatus)
    return render_template('items/list.html', items=items,
                           categories=categories, statuses=statuses,
                           search=search, selected_category=category,
                           selected_type=item_type, selected_status=selected_status)


@items_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_item():
    if request.method == 'POST':
        item_name   = request.form.get('item_name', '').strip()
        category    = request.form.get('category', '')
        item_type   = request.form.get('item_type', '')
        location    = request.form.get('location', '').strip()
        description = request.form.get('description', '').strip()

        if not all([item_name, category, item_type]):
            flash('يرجى ملء جميع الحقول المطلوبة', 'danger')
            return render_template('items/create.html', categories=list(ItemCategory))

        image_path = None
        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            image_path = save_uploaded_image(file)

        try:
            # created_at يُضبط تلقائياً من النموذج
            item = Item(
                item_name=item_name,
                category=ItemCategory(category),
                item_type=ItemType(item_type),
                status=ItemStatus.NOT_FOUND,
                location=location,
                description=description,
                image_path=image_path,
                user_id=current_user.id,
            )
            db.session.add(item)
            db.session.commit()

            if item.item_type == ItemType.LOST:
                ai_matcher.run_matching_for_item(item)

            flash('تم نشر الغرض بنجاح!', 'success')
            return redirect(url_for('items.item_detail', item_id=item.id))
        except Exception as e:
            db.session.rollback()
            flash(f'حدث خطأ: {str(e)}', 'danger')

    return render_template('items/create.html', categories=list(ItemCategory))


@items_bp.route('/<int:item_id>')
def item_detail(item_id):
    item    = Item.query.get_or_404(item_id)
    matches = []
    conversation_exists = False
    if current_user.is_authenticated and item.user_id == current_user.id:
        matches = Match.query.filter_by(source_item_id=item.id)\
                             .order_by(Match.similarity_score.desc()).limit(5).all()
    if current_user.is_authenticated and current_user.id != item.user_id:
        conversation_exists = Message.query.filter_by(item_id=item.id).filter(
            or_(Message.sender_id == current_user.id,
                Message.receiver_id == current_user.id)
        ).first() is not None
    return render_template('items/detail.html', item=item, matches=matches,
                           all_statuses=list(ItemStatus),
                           conversation_exists=conversation_exists)


@items_bp.route('/<int:item_id>/chat', methods=['POST'])
@login_required
def send_message(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id == current_user.id:
        flash('لا يمكنك إرسال رسالة إلى نفسك.', 'warning')
        return redirect(url_for('items.item_detail', item_id=item_id))

    body = request.form.get('message', '').strip()
    if not body:
        flash('يرجى كتابة رسالة قبل الإرسال.', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    message = Message(
        item_id=item.id,
        sender_id=current_user.id,
        receiver_id=item.user_id,
        body=body,
    )
    db.session.add(message)
    Notification.send(
        item.user_id,
        f'لديك رسالة جديدة من {current_user.full_name} حول المنتج "{item.item_name}".',
        link=url_for('profile.message_thread', item_id=item.id, partner_id=current_user.id)
    )
    db.session.commit()

    flash('تم إرسال الرسالة إلى صاحب المنتج.', 'success')
    return redirect(url_for('profile.message_thread', item_id=item.id, partner_id=item.user_id))


@items_bp.route('/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id and not current_user.is_admin:
        flash('غير مصرح لك بتعديل هذا الغرض', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    if request.method == 'POST':
        item.item_name   = request.form.get('item_name', item.item_name).strip()
        item.location    = request.form.get('location', item.location or '').strip()
        item.description = request.form.get('description', item.description or '').strip()
        try:
            item.category = ItemCategory(request.form.get('category', item.category.value))
        except ValueError:
            pass

        new_status_val = request.form.get('status', '')
        if new_status_val:
            try:
                item.status = ItemStatus(new_status_val)
            except ValueError:
                pass

        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            item.image_path = save_uploaded_image(file)

        if current_user.is_admin and item.user_id != current_user.id:
            Notification.send(item.user_id,
                              f'قام المسؤول بتعديل غرضك "{item.item_name}".')

        db.session.commit()
        flash('تم تحديث الغرض بنجاح', 'success')
        return redirect(url_for('items.item_detail', item_id=item_id))

    return render_template('items/edit.html', item=item,
                           categories=list(ItemCategory),
                           all_statuses=list(ItemStatus))


@items_bp.route('/<int:item_id>/update-status', methods=['POST'])
@login_required
def update_status(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id and not current_user.is_admin:
        flash('غير مصرح لك بتغيير حالة هذا الغرض', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    new_status_val = request.form.get('status', '')
    try:
        item.status = ItemStatus(new_status_val)
        if current_user.is_admin and item.user_id != current_user.id:
            Notification.send(item.user_id,
                              f'تم تحديث حالة غرضك "{item.item_name}" إلى: {item.status.value}')
        db.session.commit()
        flash(f'تم تغيير الحالة إلى: {item.status.value}', 'success')
    except ValueError:
        flash('حالة غير صحيحة', 'danger')

    return redirect(url_for('items.item_detail', item_id=item_id))


@items_bp.route('/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id and not current_user.is_admin:
        flash('غير مصرح لك بحذف هذا الغرض', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    owner_id  = item.user_id
    item_name = item.item_name
    by_admin  = current_user.is_admin and (item.user_id != current_user.id)

    deleted = item.delete_item()

    if not deleted:
        flash('لم يتم حذف الغرض. حاول مجدداً أو تواصل مع الدعم.', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    if by_admin:
        Notification.send(owner_id, f'قام المسؤول بحذف غرضك "{item_name}".')
        db.session.commit()

    flash('تم حذف الغرض', 'info')
    return redirect(url_for('items.list_items'))


@items_bp.route('/<int:item_id>/report', methods=['POST'])
@login_required
def report_item(item_id):
    item   = Item.query.get_or_404(item_id)
    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('يرجى ذكر سبب البلاغ', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    existing = Report.query.filter_by(
        reporter_id=current_user.id, item_id=item.id
    ).first()
    if existing:
        flash('لقد أرسلت بلاغاً عن هذا الغرض مسبقاً', 'warning')
        return redirect(url_for('items.item_detail', item_id=item_id))

    success = current_user.submit_report(item_id=item.id, reason=reason)
    if not success:
        flash('حدث خطأ أثناء إرسال البلاغ، حاول مرة أخرى.', 'danger')
        return redirect(url_for('items.item_detail', item_id=item_id))

    from models.user import User
    from models.report import Notification
    admins = User.query.filter_by(is_admin=True).all()
    for admin in admins:
        Notification.send(admin.id, f'تم إرسال بلاغ جديد على الغرض "{item.item_name}".')
    db.session.commit()

    flash('تم إرسال البلاغ للمراجعة', 'success')
    return redirect(url_for('items.item_detail', item_id=item_id))


@items_bp.route('/search-by-image', methods=['GET', 'POST'])
@login_required
def search_by_image():
    results = []
    if request.method == 'POST':
        file = request.files.get('image')
        if file and file.filename and allowed_file(file.filename):
            filename  = secure_filename(file.filename)
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'tmp_' + filename)
            file.save(save_path)

            target_vec = ai_matcher.request_img_details(save_path)
            all_items  = Item.query.all()

            for item in all_items:
                if item.image_path:
                    full_path = os.path.join(current_app.root_path, 'static', item.image_path)
                    item_vec  = ai_matcher.request_img_details(full_path)
                    score     = ai_matcher.compare_similarity(target_vec, item_vec)
                    if score >= ai_matcher.threshold:
                        results.append({'item': item, 'score': round(score * 100, 1)})

            results.sort(key=lambda x: x['score'], reverse=True)
            os.remove(save_path)
        else:
            flash('يرجى رفع صورة صالحة', 'danger')

    return render_template('items/search_by_image.html', results=results)
