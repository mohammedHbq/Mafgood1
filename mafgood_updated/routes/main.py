from flask import Blueprint, render_template
from models.item import Item, ItemStatus, ItemType

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    recent_lost  = Item.query.filter_by(status=ItemStatus.NOT_FOUND, item_type=ItemType.LOST)\
                             .order_by(Item.created_at.desc()).limit(6).all()
    recent_found = Item.query.filter_by(status=ItemStatus.NOT_FOUND, item_type=ItemType.FOUND)\
                             .order_by(Item.created_at.desc()).limit(6).all()
    total_items  = Item.query.count()
    resolved     = Item.query.filter_by(status=ItemStatus.FOUND_OWNER).count()
    return render_template('main/index.html',
                           recent_lost=recent_lost,
                           recent_found=recent_found,
                           total_items=total_items,
                           resolved=resolved)


@main_bp.route('/about')
def about():
    return render_template('main/about.html')
