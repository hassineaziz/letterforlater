from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, send_file, abort
from flask_login import login_required, current_user, login_user
from functools import wraps
from .models import Letter, TrustedContact, User, DeathVerification, DeathVerificationConfirmation, MediaAttachment, BlogPost
from . import db, mail
from .s3_config import s3_config
import json
from datetime import datetime, timedelta, timezone
from flask_mail import Message
from sqlalchemy import and_
from werkzeug.security import gen_salt
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import io
import base64
import tempfile
import os
import uuid

# Google OAuth imports
from google.oauth2 import id_token
from google.auth.transport import requests
import requests as http_requests

views = Blueprint('views', __name__)

def _strip_tags(html: str) -> str:
    import re
    return re.sub('<[^<]+?>', '', html or '')

def _truncate(s: str, max_len: int) -> str:
    if not s:
        return ''
    return s[:max_len]

def _prepare_excerpt(user_excerpt: str, content_html: str) -> str:
    """Ensure excerpt fits DB limit (300) and has no HTML."""
    text = user_excerpt or _strip_tags(content_html)
    text = text.strip()
    return _truncate(text, 300)

@views.route('/newsletter/subscribe', methods=['POST'])
def newsletter_subscribe():
    """Instantly subscribe a user without double opt-in and send welcome email with PDF."""
    from website.models import NewsletterSubscriber
    from website.email_service import send_newsletter_welcome_email
    import re
    from datetime import datetime, timezone
    email = (request.form.get('email') or '').strip().lower()
    source = request.form.get('source') or 'blog_sidebar'
    referer = request.headers.get('Referer') or url_for('views.blog_index')
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash('Please enter a valid email address.', 'error')
        return redirect(referer)
    try:
        subscriber = NewsletterSubscriber.query.filter_by(email=email).one_or_none()
        is_new_subscriber = not subscriber
        if not subscriber:
            subscriber = NewsletterSubscriber(
                email=email,
                source=source,
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(subscriber)
        # Set as subscribed immediately
        subscriber.status = 'subscribed'
        subscriber.confirmed_at = datetime.now(timezone.utc)
        subscriber.double_opt_in_token = None
        if not subscriber.source:
            subscriber.source = source
        db.session.commit()
        
        # Send welcome email with PDF attachment for new subscribers
        if is_new_subscriber:
            try:
                send_newsletter_welcome_email(email)
                print(f"✅ Newsletter welcome email with PDF sent to {email}")
            except Exception as email_error:
                print(f"❌ Error sending newsletter welcome email: {email_error}")
                # Don't fail the subscription if email fails
        
        flash('Subscribed! You will receive updates from our blog.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Newsletter subscribe error: {e}")
        flash('Subscription failed. Please try again later.', 'error')
    return redirect(referer)

@views.route('/newsletter/confirm')
def newsletter_confirm():
    """Confirm a subscriber via token."""
    from website.models import NewsletterSubscriber
    token = request.args.get('token')
    referer = request.headers.get('Referer') or url_for('views.blog_index')
    if not token:
        flash('Invalid confirmation link.', 'error')
        return redirect(referer)
    try:
        subscriber = NewsletterSubscriber.query.filter_by(double_opt_in_token=token).one_or_none()
        if not subscriber:
            flash('Invalid or expired confirmation link.', 'error')
            return redirect(referer)
        from datetime import datetime, timezone
        subscriber.status = 'subscribed'
        subscriber.confirmed_at = datetime.now(timezone.utc)
        subscriber.double_opt_in_token = None
        db.session.commit()
        flash('Subscription confirmed! Thank you for subscribing.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Newsletter confirm error: {e}")
        flash('Could not confirm subscription. Please try again.', 'error')
    return redirect(url_for('views.blog_index'))

@views.route('/newsletter/unsubscribe')
def newsletter_unsubscribe():
    """Unsubscribe by email or token."""
    from website.models import NewsletterSubscriber
    from datetime import datetime, timezone
    email = (request.args.get('email') or '').strip().lower()
    token = request.args.get('token')
    subscriber = None
    if token:
        subscriber = NewsletterSubscriber.query.filter_by(double_opt_in_token=token).one_or_none()
    if not subscriber and email:
        subscriber = NewsletterSubscriber.query.filter_by(email=email).one_or_none()
    if not subscriber:
        flash('Subscriber not found.', 'error')
        return redirect(url_for('views.blog_index'))
    subscriber.status = 'unsubscribed'
    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    flash('You have been unsubscribed.', 'success')
    return redirect(url_for('views.blog_index'))

@views.route('/download/legacy-template')
def download_legacy_template():
    """Public page for downloading the legacy letter template PDF"""
    return render_template('download_template.html')

@views.route('/download/legacy-template.pdf')
def serve_legacy_template_pdf():
    """Serve the PDF file directly"""
    import os
    from flask import send_file
    
    pdf_path = os.path.join(os.path.dirname(__file__), 'static', 'Legacy_Letter_Template_LetterForLater.pdf')
    
    if os.path.exists(pdf_path):
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name='Legacy_Letter_Template_LetterForLater.pdf',
            mimetype='application/pdf'
        )
    else:
        flash('PDF template not found.', 'error')
        return redirect(url_for('views.download_legacy_template'))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@views.route('/admin-cms/update-sitemap')
@admin_required
def admin_update_sitemap():
    """Update sitemap - now uses dynamic sitemap automatically"""
    try:
        # The dynamic sitemap at /sitemap.xml is automatically updated
        # No need to run scripts - just confirm it's working
        flash('Sitemap is automatically updated! Visit /sitemap.xml to see current sitemap.', 'success')
        
        # Optional: Also update static sitemap for backup
        import subprocess
        import os
        
        script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'update_sitemap.py')
        result = subprocess.run(['python3', script_path], capture_output=True, text=True)
        
        if result.returncode == 0:
            flash('Static sitemap backup also updated successfully!', 'info')
        else:
            flash(f'Static sitemap backup failed: {result.stderr}', 'warning')
            
    except Exception as e:
        flash(f'Error updating sitemap: {str(e)}', 'error')
    
    return redirect(url_for('views.blog_dashboard'))

@views.route('/admin-cms/newsletter/export.csv')
@admin_required
def admin_export_newsletter():
    """Export subscribers as CSV (subscribed only by default)."""
    from website.models import NewsletterSubscriber
    import csv
    from io import StringIO
    status = request.args.get('status', 'subscribed')
    q = NewsletterSubscriber.query
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(NewsletterSubscriber.created_at.desc()).all()
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['email', 'status', 'source', 'confirmed_at', 'unsubscribed_at', 'created_at'])
    for r in rows:
        writer.writerow([r.email, r.status, r.source or '', r.confirmed_at or '', r.unsubscribed_at or '', r.created_at])
    output = si.getvalue()
    from flask import Response
    return Response(output, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=subscribers.csv'})

@views.route('/unsubscribe', methods=['GET', 'POST'])
@login_required
def unsubscribe():
    """Unsubscribe logged-in user from marketing emails after confirmation."""
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'confirm':
            try:
                current_user.marketing_consent = False
                db.session.commit()
                flash('You have successfully unsubscribed from marketing emails.', 'success')
                return redirect(url_for('views.settings'))
            except Exception as e:
                db.session.rollback()
                flash('An error occurred. Please try again.', 'error')
                print(f"Error updating marketing_consent: {str(e)}")
        else:
            flash('Glad to have you stay! Your preferences are unchanged.', 'info')
            return redirect(url_for('views.settings'))
    # GET: show confirmation page
    return render_template('unsubscribe.html')

def has_active_trusted_relationships(user):
    """Check if a user has active (confirmed) trusted contact relationships"""
    if not user or not user.is_authenticated:
        return False
    
    # Check if user is a confirmed trusted contact for someone else
    active_contacts = TrustedContact.query.filter_by(
        email=user.email,
        is_confirmed=True
    ).count()
    
    return active_contacts > 0

def create_notification(user_id, notification_type, title, message, related_user_id=None, related_letter_id=None, related_trusted_contact_id=None):
    """Helper function to create notifications"""
    from website.models import Notification
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_user_id=related_user_id,
        related_letter_id=related_letter_id,
        related_trusted_contact_id=related_trusted_contact_id
    )
    db.session.add(notification)
    try:
        db.session.commit()
        return notification
    except Exception as e:
        db.session.rollback()
        print(f"Error creating notification: {e}")
        return None

def send_letter_invite(letter, recipient_email, recipient_name, author_name):
    """Send an invite email instead of the full letter content"""
    try:
        from website.models import RecipientInvite
        from flask import url_for, render_template
        import os
        
        # Create or get existing invite record
        invite = RecipientInvite.query.filter_by(
            letter_id=letter.id,
            recipient_email=recipient_email
        ).first()
        
        if not invite:
            invite = RecipientInvite(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                letter_id=letter.id
            )
            db.session.add(invite)
            db.session.flush()
        
        # Create the email message
        msg = Message(
            f'{author_name} has left you a personal letter - LetterForLater',
            recipients=[recipient_email],
            sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
        )
        
        # Build invite URL
        invite_url = url_for('auth.sign_up_with_invite', token=invite.invite_token, _external=True)
        
        # Add tracking pixel for email opens
        tracking_pixel_url = url_for('views.track_email_open', token=invite.invite_token, _external=True)
        
        # Render HTML template
        msg.html = render_template('emails/letter_received.html',
            recipient_name=recipient_name,
            author_name=author_name,
            invite_url=invite_url,
            tracking_pixel_url=tracking_pixel_url
        )
        
        # Render text template
        msg.body = render_template('emails/letter_received.txt',
            recipient_name=recipient_name,
            author_name=author_name,
            invite_url=invite_url
        )
        
        mail.send(msg)
        
        # Update invite record
        invite.sent_at = datetime.now(timezone.utc)
        db.session.commit()
        
        print(f"Invite email sent to {recipient_email} for letter {letter.id}")
        return True
        
    except Exception as e:
        print(f"Error sending letter invite: {str(e)}")
        db.session.rollback()
        return False

def send_letter_with_media(letter, recipient_email, recipient_name, author_name):
    """Legacy function - now redirects to invite system"""
    return send_letter_invite(letter, recipient_email, recipient_name, author_name)

@views.context_processor
def utility_processor():
    """Make utility functions available to all templates"""
    def check_trusted_contact_status(user):
        """Check if user has active trusted contact relationships"""
        if not user or not user.is_authenticated:
            return False
        return has_active_trusted_relationships(user)
    
    def has_received_letters(user):
        """Check if user has received any letters"""
        if not user or not user.is_authenticated:
            return False
        from website.models import RecipientInvite
        received_count = RecipientInvite.query.filter(
            RecipientInvite.recipient_user_id == user.id,
            RecipientInvite.registered_at.isnot(None)
        ).count()
        return received_count > 0
    
    return dict(check_trusted_contact_status=check_trusted_contact_status, has_received_letters=has_received_letters)

def generate_unique_slug(base_title: str) -> str:
    import re
    base_slug = re.sub(r'[^a-z0-9]+', '-', base_title.strip().lower())
    base_slug = base_slug.strip('-') or 'post'
    slug = base_slug
    counter = 2
    while BlogPost.query.filter_by(slug=slug).first() is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

# Media upload configuration (moved to media_handlers.py)

# Media processing functions (moved to media_handlers.py)
        


@views.route('/', methods=['GET'])
def home():
    """Home page - landing page when logged out, dashboard when logged in"""
    if current_user.is_authenticated:
        return render_template("home.html", user=current_user)
    else:
        return render_template("landing.html")

# ===== STATIC LEGAL PAGES =====
@views.route('/privacy')
def privacy_policy():
    return render_template('privacy.html', user=current_user)

@views.route('/terms')
def terms_of_service():
    return render_template('terms.html', user=current_user)

# ===== BLOG CMS =====

# Public Blog Routes
@views.route('/blog')
def blog_index():
    """Public blog index with search and tag filters"""
    page = int(request.args.get('page', 1))
    per_page = 10
    search = request.args.get('search', '').strip()
    tag = request.args.get('tag', '').strip()
    
    # Build query
    query = BlogPost.query.filter_by(status='published')
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                BlogPost.title.ilike(f'%{search}%'),
                BlogPost.content_html.ilike(f'%{search}%'),
                BlogPost.excerpt.ilike(f'%{search}%')
            )
        )
    
    # Apply tag filter
    if tag:
        query = query.filter(BlogPost.tags.contains([tag]))
    
    # Order by published date
    query = query.order_by(BlogPost.published_at.desc().nullslast(), BlogPost.created_at.desc())
    
    posts = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all unique tags for filter
    all_tags = db.session.query(BlogPost.tags).filter_by(status='published').all()
    unique_tags = set()
    for tag_row in all_tags:
        if tag_row[0]:
            unique_tags.update(tag_row[0])
    
    return render_template('blog_index.html', 
                         user=current_user, 
                         posts=posts.items, 
                         pagination=posts,
                         search=search,
                         current_tag=tag,
                         all_tags=sorted(unique_tags))

@views.route('/blog/<slug>')
def blog_post(slug):
    """Individual blog post page"""
    post = BlogPost.query.filter_by(slug=slug, status='published').first_or_404()
    # Compute estimated read time (~200 wpm)
    try:
        plain = _strip_tags(post.content_html or '')
        words = len(plain.split()) if plain else 0
        read_minutes = max(1, round(words / 200))
    except Exception:
        read_minutes = 5
    return render_template('blog_post.html', user=current_user, post=post, read_minutes=read_minutes)

@views.route('/blog/feed.xml')
def blog_feed():
    """RSS feed for blog posts"""
    posts = BlogPost.query.filter_by(status='published').order_by(
        BlogPost.published_at.desc().nullslast()
    ).limit(10).all()
    
    return render_template('blog_feed.xml', posts=posts), 200, {'Content-Type': 'application/xml'}

# Admin Blog Routes
@views.route('/admin-cms')
@login_required
@admin_required
def blog_dashboard():
    """Admin dashboard for blog management"""
    page = int(request.args.get('page', 1))
    per_page = 20
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    
    # Build query
    query = BlogPost.query
    
    # Apply search filter
    if search:
        query = query.filter(
            db.or_(
                BlogPost.title.ilike(f'%{search}%'),
                BlogPost.content_html.ilike(f'%{search}%'),
                BlogPost.excerpt.ilike(f'%{search}%')
            )
        )
    
    # Apply status filter
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    # Apply tag filter
    if tag_filter:
        query = query.filter(BlogPost.tags.contains([tag_filter]))
    
    # Order by updated date
    query = query.order_by(BlogPost.updated_at.desc())
    
    posts = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get stats
    total_posts = BlogPost.query.count()
    published_posts = BlogPost.query.filter_by(status='published').count()
    draft_posts = BlogPost.query.filter_by(status='draft').count()
    
    # Get all unique tags
    all_tags = db.session.query(BlogPost.tags).all()
    unique_tags = set()
    for tag_row in all_tags:
        if tag_row[0]:
            unique_tags.update(tag_row[0])
    
    return render_template('blog_admin_dashboard.html',
                         user=current_user,
                         posts=posts.items,
                         pagination=posts,
                         search=search,
                         status_filter=status_filter,
                         tag_filter=tag_filter,
                         all_tags=sorted(unique_tags),
                         stats={
                             'total': total_posts,
                             'published': published_posts,
                             'drafts': draft_posts
                         })

@views.route('/admin-cms/new', methods=['GET', 'POST'])
@login_required
@admin_required
def blog_new():
    """Create new blog post"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip()
        content_html = request.form.get('content_html', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        cover_image_url = request.form.get('cover_image_url', '').strip()
        meta_title = request.form.get('meta_title', '').strip() or title
        meta_description = request.form.get('meta_description', '').strip() or excerpt
        focus_keyword = request.form.get('focus_keyword', '').strip()
        # Handle status based on action button
        action = request.form.get('action', 'save_draft')
        status = 'published' if action == 'publish' else 'draft'
        tags_input = request.form.get('tags', '').strip()
        publish_date = request.form.get('publish_date', '').strip()
        
        if not title or not content_html:
            flash('Title and content are required.', 'error')
            return redirect(url_for('views.blog_new'))
        
        # Generate slug if not provided
        if not slug:
            slug = generate_unique_slug(title)
        else:
            # Clean and validate slug
            slug = generate_unique_slug(slug)
        
        # Handle publish date
        published_at = None
        if status == 'published':
            if publish_date:
                try:
                    published_at = datetime.strptime(publish_date, '%Y-%m-%dT%H:%M')
                except ValueError:
                    published_at = datetime.now(timezone.utc)
            else:
                published_at = datetime.now(timezone.utc)
        
        # Create post
        post = BlogPost(
            slug=slug,
            title=title,
            excerpt=_prepare_excerpt(excerpt, content_html),
            content_html=content_html,
            cover_image_url=cover_image_url or None,
            status=status,
            published_at=published_at,
            author_id=current_user.id,
            meta_title=meta_title,
            meta_description=meta_description,
            focus_keyword=focus_keyword,
        )
        
        # Handle tags
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            post.set_tags_list(tags_list)
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('views.blog_dashboard'))
    
    return render_template('blog_admin_edit.html', user=current_user, post=None)

@views.route('/admin-cms/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def blog_edit(post_id):
    """Edit existing blog post"""
    post = BlogPost.query.get_or_404(post_id)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        slug = request.form.get('slug', '').strip()
        content_html = request.form.get('content_html', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        cover_image_url = request.form.get('cover_image_url', '').strip()
        meta_title = request.form.get('meta_title', '').strip() or title
        meta_description = request.form.get('meta_description', '').strip() or excerpt
        focus_keyword = request.form.get('focus_keyword', '').strip()
        # Handle status based on action button
        action = request.form.get('action', 'save_draft')
        status = 'published' if action == 'publish' else 'draft'
        tags_input = request.form.get('tags', '').strip()
        publish_date = request.form.get('publish_date', '').strip()
        
        if not title or not content_html:
            flash('Title and content are required.', 'error')
            return redirect(url_for('views.blog_edit', post_id=post.id))
        
        # Update slug if changed
        if slug and slug != post.slug:
            post.slug = generate_unique_slug(slug)
        
        # Update fields
        post.title = title
        post.content_html = content_html
        post.excerpt = _prepare_excerpt(excerpt, content_html)
        post.cover_image_url = cover_image_url or None
        post.meta_title = meta_title
        post.meta_description = meta_description
        post.focus_keyword = focus_keyword
        
        # Handle status and publish date
        prev_status = post.status
        post.status = status
        
        if status == 'published' and not post.published_at:
            if publish_date:
                try:
                    post.published_at = datetime.strptime(publish_date, '%Y-%m-%dT%H:%M')
                except ValueError:
                    post.published_at = datetime.now(timezone.utc)
            else:
                post.published_at = datetime.now(timezone.utc)
        elif status == 'draft':
            post.published_at = None
        
        # Handle tags
        if tags_input:
            tags_list = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
            post.set_tags_list(tags_list)
        else:
            post.set_tags_list([])
        
        db.session.commit()
        flash('Post updated successfully!', 'success')
        return redirect(url_for('views.blog_dashboard'))
    
    return render_template('blog_admin_edit.html', user=current_user, post=post)

@views.route('/admin-cms/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def blog_delete(post_id):
    """Delete a blog post (admin only)"""
    post = BlogPost.query.get_or_404(post_id)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Post deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting post {post_id}: {str(e)}")
        flash('Failed to delete post.', 'error')
    return redirect(url_for('views.blog_dashboard'))

@views.route('/admin-cms/upload-image-url', methods=['POST'])
@login_required
@admin_required
def blog_upload_image_url():
    """Generate presigned URL for blog image upload"""
    data = request.get_json()
    filename = data.get('filename')
    
    if not filename:
        return jsonify({'error': 'Filename required'}), 400
    
    return s3_media_handler.generate_blog_upload_url(filename)

@views.route('/blog-images/<path:filename>')
def serve_blog_image(filename):
    """Serve blog images from S3 - redirects to S3 presigned URL"""
    try:
        # Get the S3 key for the blog image
        folder_path = s3_config.get_blog_folder()
        s3_key = s3_config.get_file_key(folder_path, filename)
        
        # Generate presigned URL for the image
        presigned_url = s3_config.generate_presigned_download_url(s3_key)
        
        # Redirect to S3 URL
        return redirect(presigned_url)
        
    except Exception as e:
        print(f"Error serving blog image {filename}: {str(e)}")
        return "Image not found", 404


@views.route('/admin-cms/feed-preview')
@login_required
@admin_required
def blog_feed_preview():
    """Preview RSS feed"""
    posts = BlogPost.query.filter_by(status='published').order_by(
        BlogPost.published_at.desc().nullslast()
    ).limit(10).all()
    
    return render_template('blog_feed.xml', posts=posts), 200, {'Content-Type': 'application/xml'}

# Remove custom TinyMCE static route; Flask serves from /static automatically

@views.route('/add-letter', methods=['GET', 'POST'])
@login_required
def add_letter():
    """Add new letter page - also supports editing when letter_id is provided"""
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if request.method == 'POST':
        # If editing an existing letter
        letter_id = request.form.get('letter_id')
        if letter_id:
            letter = Letter.query.get(letter_id)
            if not letter or letter.user_id != current_user.id:
                if is_ajax:
                    return jsonify({'success': False, 'error': 'You do not have permission to edit this letter.'}), 403
                flash('You do not have permission to edit this letter.', 'error')
                return redirect(url_for('views.view_letters', user_id=current_user.id))

            # Update fields
            letter.title = request.form.get('title')
            letter.content = request.form.get('content')
            letter.recipient_name = request.form.get('recipient_name')
            letter.recipient_email = request.form.get('recipient_email')
            delivery_type = request.form.get('delivery_type')
            letter.delivery_type = delivery_type

            # Delivery specifics
            if delivery_type == 'date':
                scheduled_date = request.form.get('scheduled_date')
                if scheduled_date:
                    letter.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
                    letter.delivery_status = 'pending'
                    letter.status = 'scheduled'
                else:
                    letter.delivery_date = None
                    letter.delivery_status = None
            elif delivery_type == 'death_verification':
                letter.status = 'pending_verification'
                letter.delivery_date = None
                letter.delivery_status = None
                # Delay handling
                delay_option = request.form.get('delay_option', 'immediate')
                if delay_option == 'immediate':
                    letter.delay_after_verification = 0
                elif delay_option == '1_day':
                    letter.delay_after_verification = 1
                elif delay_option == '1_week':
                    letter.delay_after_verification = 7
                elif delay_option == '1_month':
                    letter.delay_after_verification = 30
                elif delay_option == 'custom':
                    custom_days = request.form.get('custom_delay_days')
                    if custom_days and custom_days.isdigit():
                        days = int(custom_days)
                        if 1 <= days <= 365:
                            letter.delay_after_verification = days
                        else:
                            error_msg = 'Custom delay must be between 1 and 365 days.'
                            if is_ajax:
                                return jsonify({'success': False, 'error': error_msg}), 400
                            flash(error_msg, 'error')
                            return redirect(url_for('views.add_letter', letter_id=letter.id))
                    else:
                        error_msg = 'Please enter a valid number of days for custom delay.'
                        if is_ajax:
                            return jsonify({'success': False, 'error': error_msg}), 400
                        flash(error_msg, 'error')
                        return redirect(url_for('views.add_letter', letter_id=letter.id))

            # Handle media attachments for edited letters
            # First, get the list of media IDs that should be attached to this letter
            media_attachments_data = request.form.get('media_attachments')
            current_media_ids = set()
            
            if media_attachments_data:
                try:
                    media_attachments = json.loads(media_attachments_data)
                    current_media_ids = {media_info.get('media_id') for media_info in media_attachments if media_info.get('media_id')}
                except Exception as e:
                    print(f"Error parsing media attachments during edit: {e}")
            
            # Get existing media attachments for this letter
            existing_media = MediaAttachment.query.filter_by(letter_id=letter.id).all()
            existing_media_ids = {media.id for media in existing_media}
            
            # Find media to remove (existing media not in current list)
            media_to_remove = existing_media_ids - current_media_ids
            if media_to_remove:
                try:
                    # Remove media from letter by deleting MediaAttachment records
                    media_to_delete = MediaAttachment.query.filter(
                        MediaAttachment.id.in_(list(media_to_remove)),
                        MediaAttachment.letter_id == letter.id,
                        MediaAttachment.user_id == current_user.id
                    ).all()
                    for media in media_to_delete:
                        db.session.delete(media)
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Error removing media attachments during edit: {e}")
            
            # Find media to add (current media not in existing list)
            media_to_add = current_media_ids - existing_media_ids
            if media_to_add:
                try:
                    # Attach media to letter by updating letter_id
                    media_to_attach = MediaAttachment.query.filter(
                        MediaAttachment.id.in_(list(media_to_add)),
                        MediaAttachment.user_id == current_user.id
                    ).all()
                    for media in media_to_attach:
                        media.letter_id = letter.id
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"Error attaching media to letter during edit: {e}")

            try:
                db.session.commit()
                if is_ajax:
                    redirect_url = url_for('views.view_letters', user_id=current_user.id)
                    response = jsonify({'success': True, 'message': 'Letter updated successfully!', 'redirect': redirect_url})
                    response.headers['Content-Type'] = 'application/json'
                    return response
                flash('Letter updated successfully!', 'success')
                return redirect(url_for('views.view_letters', user_id=current_user.id))
            except Exception as e:
                db.session.rollback()
                error_msg = f'An error occurred while updating the letter: {str(e)}'
                print(f"Error updating letter: {e}")
                if is_ajax:
                    return jsonify({'success': False, 'error': error_msg}), 500
                flash('An error occurred while updating the letter.', 'error')
                return redirect(url_for('views.view_letters', user_id=current_user.id))

        # Otherwise, create a new letter
        title = request.form.get('title')
        content = request.form.get('content')
        recipient_name = request.form.get('recipient_name')
        recipient_email = request.form.get('recipient_email')
        delivery_type = request.form.get('delivery_type')

        if not title or not content or not recipient_name or not recipient_email or not delivery_type:
            error_msg = 'Please fill in all required fields.'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('views.add_letter'))

        new_letter = Letter(
            title=title,
            content=content,
            recipient_name=recipient_name,
            recipient_email=recipient_email,
            delivery_type=delivery_type,
            user_id=current_user.id
        )
        db.session.add(new_letter)
        db.session.flush()

        if delivery_type == 'date':
            scheduled_date = request.form.get('scheduled_date')
            if not scheduled_date:
                error_msg = 'Please select a delivery date.'
                if is_ajax:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                db.session.rollback()
                return redirect(url_for('views.add_letter'))
            # Set delivery time to 8 PM (20:00) in user's local timezone
            new_letter.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
            new_letter.delivery_status = 'pending'
            new_letter.status = 'scheduled'
        elif delivery_type == 'death_verification':
            # Check if user has confirmed trusted contacts
            confirmed_contacts = TrustedContact.query.filter_by(
                user_id=current_user.id, 
                is_confirmed=True
            ).count()
            
            if confirmed_contacts == 0:
                error_msg = 'You need at least one confirmed trusted contact to use death verification delivery. Please add trusted contacts first.'
                if is_ajax:
                    db.session.rollback()
                    return jsonify({'success': False, 'error': error_msg}), 400
                flash(error_msg, 'error')
                db.session.rollback()
                return redirect(url_for('views.add_letter'))
            
            # Set status to pending verification
            new_letter.status = 'pending_verification'
            
            # Handle delay after death verification
            delay_option = request.form.get('delay_option', 'immediate')
            if delay_option == 'immediate':
                new_letter.delay_after_verification = 0
            elif delay_option == '1_day':
                new_letter.delay_after_verification = 1
            elif delay_option == '1_week':
                new_letter.delay_after_verification = 7
            elif delay_option == '1_month':
                new_letter.delay_after_verification = 30
            elif delay_option == 'custom':
                custom_days = request.form.get('custom_delay_days')
                if custom_days and custom_days.isdigit():
                    days = int(custom_days)
                    if 1 <= days <= 365:
                        new_letter.delay_after_verification = days
                    else:
                        error_msg = 'Custom delay must be between 1 and 365 days.'
                        if is_ajax:
                            db.session.rollback()
                            return jsonify({'success': False, 'error': error_msg}), 400
                        flash(error_msg, 'error')
                        db.session.rollback()
                        return redirect(url_for('views.add_letter'))
                else:
                    error_msg = 'Please enter a valid number of days for custom delay.'
                    if is_ajax:
                        db.session.rollback()
                        return jsonify({'success': False, 'error': error_msg}), 400
                    flash(error_msg, 'error')
                    db.session.rollback()
                    return redirect(url_for('views.add_letter'))
            
            # Create or get death verification record for this user
            existing_verification = DeathVerification.query.filter_by(user_id=current_user.id).first()
            if not existing_verification:
                death_verification = DeathVerification(
                    user_id=current_user.id,
                    confirmations_count=0,
                    status='pending',
                    verification_code=str(uuid.uuid4())
                )
                db.session.add(death_verification)

        try:
            db.session.commit()
            
            # Media attachments are now handled during upload with letter_id
            # No need to process them here as they're already attached to the letter
            
            # Delete any existing draft since the letter was successfully created
            draft = Letter.query.filter_by(user_id=current_user.id, status='draft').first()
            if draft:
                db.session.delete(draft)
                db.session.commit()
            
            if is_ajax:
                redirect_url = url_for('views.view_letters', user_id=current_user.id)
                response = jsonify({'success': True, 'message': 'Letter created successfully!', 'redirect': redirect_url})
                response.headers['Content-Type'] = 'application/json'
                return response
            flash('Letter created successfully!', 'success')
            return redirect(url_for('views.view_letters', user_id=current_user.id))
        except Exception as e:
            db.session.rollback()
            error_msg = f'An error occurred while creating the letter: {str(e)}'
            print(f"Error creating letter: {str(e)}")
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 500
            flash('An error occurred while creating the letter.', 'error')
            return redirect(url_for('views.add_letter'))
    # GET request - render form, optionally with an existing letter loaded
    # Ensure any previous transaction errors are rolled back before starting
    try:
        db.session.rollback()
    except Exception:
        pass  # Ignore if no transaction exists
    
    letter_id = request.args.get('letter_id')
    letter_to_edit = None
    media_attachments = []
    if letter_id:
        try:
            letter_to_edit = Letter.query.get(letter_id)
            if not letter_to_edit or letter_to_edit.user_id != current_user.id:
                flash('You do not have permission to edit this letter.', 'error')
                return redirect(url_for('views.view_letters', user_id=current_user.id))
            try:
                media_attachments = MediaAttachment.query.filter_by(letter_id=letter_to_edit.id).all()
            except Exception as e:
                db.session.rollback()
                print(f"Error loading media attachments: {e}")
                media_attachments = []
        except Exception as e:
            db.session.rollback()
            print(f"Error loading letter: {e}")
            flash('Error loading letter. Please try again.', 'error')
            return redirect(url_for('views.view_letters', user_id=current_user.id))

    try:
        confirmed_contacts = current_user.trusted_contacts_list.filter_by(is_confirmed=True).all()
    except Exception as e:
        db.session.rollback()
        print(f"Error loading trusted contacts: {e}")
        confirmed_contacts = []  # Default to empty list on error
    return render_template(
        "add_letter.html",
        user=current_user,
        now=datetime.now(timezone.utc),
        confirmed_contacts=confirmed_contacts,
        letter_to_edit=letter_to_edit,
        media_attachments=media_attachments
    )

@views.route('/verify-death', methods=['GET', 'POST'])
@login_required
def verify_death():
    # Check if user is a confirmed trusted contact for someone
    active_contacts = TrustedContact.query.filter_by(
        email=current_user.email,
        is_confirmed=True
    ).count()
    
    if active_contacts == 0:
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('views.home'))
    # Find all users who have added current_user as a trusted contact and are confirmed
    trusted_for = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=True).all()
    verification_info = []
    for contact in trusted_for:
        # Only show if the trusted contact is confirmed
        if not contact.is_confirmed:
            continue
        
        # Check if there are letters requiring death verification for this user
        has_death_verification_letters = Letter.query.filter_by(
            user_id=contact.user_id, 
            delivery_type='death_verification'
        ).first() is not None
        
        # Find any DeathVerification record for this user
        dv = DeathVerification.query.filter_by(user_id=contact.user_id).order_by(DeathVerification.id.desc()).first()
        
        if dv:
            # Find this trusted contact's confirmation (if any)
            confirmation = DeathVerificationConfirmation.query.filter_by(verification_id=dv.id, trusted_contact_id=contact.id).first()
            if confirmation:
                status = 'confirmed' if confirmation.confirmed else 'rejected'
            elif contact.is_in_death_confirmation_cooldown():
                status = 'cooldown'
            else:
                status = dv.status
        elif has_death_verification_letters:
            # Check if in cooldown
            if contact.is_in_death_confirmation_cooldown():
                status = 'cooldown'
            else:
                # There are letters requiring death verification but no verification record yet
                # Create a new verification record
                dv = DeathVerification(
                    user_id=contact.user_id,
                    confirmations_count=0,
                    status='pending',
                    verification_code=str(uuid.uuid4())
                )
                db.session.add(dv)
                db.session.flush()  # Get the ID
                status = 'pending'
        else:
            # No letters requiring death verification
            status = 'no_letters'
            
        verification_info.append({
            'user': contact.user,
            'verification': dv,
            'trusted_contact': contact,
            'status': status
        })
    if request.method == 'POST':
        verification_id = request.form.get('verification_id')
        action = request.form.get('action')
        trusted_contact_id = request.form.get('trusted_contact_id')
        
        # Get the trusted contact
        contact = TrustedContact.query.get(trusted_contact_id)
        if not contact or contact.email != current_user.email:
            flash('Invalid verification request.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Only allow confirmation for users who explicitly trusted this contact
        if not contact.is_confirmed:
            flash('You are not a confirmed trusted contact for this user.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Check if this trusted contact is in cooldown
        if contact.is_in_death_confirmation_cooldown():
            flash('You are currently in a 7-day cooldown period and cannot confirm death for this user.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Get or create the verification record
        verification = None
        if verification_id:
            verification = DeathVerification.query.get(verification_id)
        else:
            # Check if there are letters requiring death verification
            has_death_verification_letters = Letter.query.filter_by(
                user_id=contact.user_id, 
                delivery_type='death_verification'
            ).first() is not None
            
            if has_death_verification_letters:
                # Create a new verification record
                verification = DeathVerification(
                    user_id=contact.user_id,
                    confirmations_count=0,
                    status='pending',
                    verification_code=str(uuid.uuid4())
                )
                db.session.add(verification)
                db.session.flush()  # Get the ID
            else:
                flash('No letters requiring death verification found.', 'error')
                return redirect(url_for('views.verify_death'))
        
        if not verification:
            flash('Invalid verification request.', 'error')
            return redirect(url_for('views.verify_death'))
            
        # Prevent duplicate confirmations
        existing = DeathVerificationConfirmation.query.filter_by(verification_id=verification.id, trusted_contact_id=contact.id).first()
        if existing:
            flash('You have already responded to this verification.', 'info')
            return redirect(url_for('views.verify_death'))
        if action == 'confirm':
            conf = DeathVerificationConfirmation(
                verification_id=verification.id,
                trusted_contact_id=contact.id,
                confirmed=True
            )
            db.session.add(conf)
            verification.confirmations_count += 1
            verification.verification_date = datetime.now(timezone.utc)

            # Calculate 50% threshold of total trusted contacts (must be before using below)
            total_trusted_contacts = TrustedContact.query.filter_by(
                user_id=verification.user_id, 
                is_confirmed=True
            ).count()
            required_confirmations = max(1, (total_trusted_contacts + 1) // 2)  # +1 to round up

            # Create notification for the main user about death confirmation
            main_user = User.query.get(verification.user_id)
            if main_user:
                if verification.confirmations_count >= required_confirmations:
                    # Letters have been processed automatically
                    notification_title = f"Death Confirmation Complete - Letters Processed"
                    notification_message = f"{verification.confirmations_count} trusted contacts have confirmed your death. Your letters have been processed according to their delivery settings."
                    
                    # Send email notification about letters being processed
                    if main_user.notification_preferences.get('email_notifications', True):
                        try:
                            msg = Message(
                                'Death Confirmation Complete - LetterForLater Letters Processed',
                                recipients=[main_user.email],
                                sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
                            )
                            
                            # Render HTML template
                            msg.html = render_template('emails/death_confirmation_complete.html',
                                user_name=f"{main_user.first_name} {main_user.last_name}",
                                user_email=main_user.email,
                                confirmations_count=verification.confirmations_count
                            )
                            
                            # Render text template
                            msg.body = render_template('emails/death_confirmation_complete.txt',
                                user_name=f"{main_user.first_name} {main_user.last_name}",
                                user_email=main_user.email,
                                confirmations_count=verification.confirmations_count
                            )
                            
                            mail.send(msg)
                        except Exception as e:
                            print(f"Error sending death confirmation email: {str(e)}")
                else:
                    # Still waiting for more confirmations
                    notification_title = f"Death Confirmation from {contact.full_name}"
                    notification_message = f"{contact.full_name} has confirmed your death. Waiting for more trusted contacts to confirm before processing letters."
                    
                    # Send email notification if user has email notifications enabled
                    if main_user.notification_preferences.get('email_notifications', True):
                        try:
                            msg = Message(
                                'Death Confirmation Alert - LetterForLater',
                                recipients=[main_user.email],
                                sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
                            )
                            
                            # Render HTML template
                            msg.html = render_template('emails/death_confirmation_alert.html',
                                user_name=f"{main_user.first_name} {main_user.last_name}",
                                user_email=main_user.email,
                                confirmer_name=contact.full_name,
                                confirmations_count=verification.confirmations_count
                            )
                            
                            # Render text template
                            msg.body = render_template('emails/death_confirmation_alert.txt',
                                user_name=f"{main_user.first_name} {main_user.last_name}",
                                user_email=main_user.email,
                                confirmer_name=contact.full_name,
                                confirmations_count=verification.confirmations_count
                            )
                            
                            mail.send(msg)
                        except Exception as e:
                            print(f"Error sending death confirmation email: {str(e)}")
                
                # Create notification
                create_notification(
                    user_id=main_user.id,
                    notification_type='death_verification_confirmation',
                    title=notification_title,
                    message=notification_message,
                    related_trusted_contact_id=contact.id
                )
            
            # required_confirmations already computed above
            
            if verification.confirmations_count >= required_confirmations:
                # Process letters automatically based on their delay settings
                verification.status = 'verified'
                
                # Process all pending_verification letters for this user
                letters = Letter.query.filter_by(user_id=verification.user_id, status='pending_verification').all()
                for letter in letters:
                    if letter.delay_after_verification == 0:
                        # Send immediately with media attachments
                        try:
                            success = send_letter_with_media(
                                letter, 
                                letter.recipient_email, 
                                letter.recipient_name, 
                                f"{letter.author.first_name} {letter.author.last_name}"
                            )
                            if success:
                                letter.status = 'delivered'
                                letter.delivery_date = datetime.now(timezone.utc)
                                letter.delivery_status = 'delivered'
                                print(f"Letter {letter.id} sent with media to {letter.recipient_email}")
                            else:
                                print(f"Failed to send letter {letter.id} to {letter.recipient_email}")
                        except Exception as e:
                            print(f"Error sending letter to {letter.recipient_email}: {str(e)}")
                            letter.status = 'delivered'
                            letter.delivery_date = datetime.now(timezone.utc)
                            letter.delivery_status = 'delivered'
                    else:
                        # Schedule for later delivery
                        delivery_date = datetime.now(timezone.utc) + timedelta(days=letter.delay_after_verification)
                        letter.delivery_date = delivery_date
                        letter.delivery_status = 'scheduled'
                        letter.status = 'scheduled'
                        print(f"Letter {letter.id} scheduled for delivery on {delivery_date}")
                
                flash(f'Death confirmation recorded. {verification.confirmations_count}/{total_trusted_contacts} trusted contacts confirmed. Letters have been processed according to their delay settings.', 'success')
            else:
                flash(f'Death confirmation recorded. {verification.confirmations_count}/{required_confirmations} confirmations needed. Waiting for more trusted contacts to confirm.', 'info')
        elif action == 'reject':
            conf = DeathVerificationConfirmation(
                verification_id=verification.id,
                trusted_contact_id=contact.id,
                confirmed=False
            )
            db.session.add(conf)
            verification.status = 'rejected'
            verification.verification_date = datetime.now(timezone.utc)
        try:
            db.session.commit()
            flash('Verification status updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating verification status.', 'error')
            print(f"Error updating verification: {str(e)}")
        return redirect(url_for('views.verify_death'))
    return render_template("verify_death.html", verifications=verification_info, user=current_user)

@views.route('/respond-to-death-verification', methods=['POST'])
@login_required
def respond_to_death_verification():
    """Main user responds to death verification (accept or deny)"""
    action = request.form.get('action')  # 'accept' or 'deny'
    verification_id = request.form.get('verification_id')
    
    if not action or not verification_id:
        flash('Invalid request.', 'error')
        return redirect(url_for('views.home'))
    
    # Find the death verification
    verification = DeathVerification.query.get(verification_id)
    if not verification or verification.user_id != current_user.id:
        flash('You do not have permission to respond to this verification.', 'error')
        return redirect(url_for('views.home'))
    
    if verification.status not in ['pending_main_user_response', 'verified']:
        flash('This verification is not waiting for your response.', 'error')
        return redirect(url_for('views.home'))
    
    if action == 'accept':
        # Accept the death verification and process letters
        verification.status = 'verified'
        
        # Process all pending_verification letters for this user
        letters = Letter.query.filter_by(user_id=verification.user_id, status='pending_verification').all()
        for letter in letters:
            if letter.delay_after_verification == 0:
                # Send immediately with media attachments
                try:
                    success = send_letter_with_media(
                        letter, 
                        letter.recipient_email, 
                        letter.recipient_name, 
                        f"{letter.author.first_name} {letter.author.last_name}"
                    )
                    if success:
                        letter.status = 'delivered'
                        letter.delivery_date = datetime.now(timezone.utc)
                        letter.delivery_status = 'delivered'
                        print(f"Letter {letter.id} sent with media to {letter.recipient_email}")
                    else:
                        print(f"Failed to send letter {letter.id} to {letter.recipient_email}")
                except Exception as e:
                    print(f"Error sending letter to {letter.recipient_email}: {str(e)}")
                    letter.status = 'delivered'
                    letter.delivery_date = datetime.now(timezone.utc)
                    letter.delivery_status = 'delivered'
            else:
                # Schedule for later delivery
                delivery_date = datetime.now(timezone.utc) + timedelta(days=letter.delay_after_verification)
                letter.delivery_date = delivery_date
                letter.delivery_status = 'scheduled'
                letter.status = 'scheduled'
                print(f"Letter {letter.id} scheduled for delivery on {delivery_date}")
        
        flash('Death verification accepted. Letters have been processed according to your chosen delay settings.', 'success')
        
    elif action == 'deny':
        # Check if letters were already processed before changing status
        letters_were_processed = verification.status == 'verified'
        
        # Deny the death verification and reset confirmations
        verification.status = 'denied'
        verification.confirmations_count = 0
        
        # If letters were already processed, cancel any scheduled deliveries
        if letters_were_processed:
            # Cancel any scheduled letters
            scheduled_letters = Letter.query.filter_by(
                user_id=verification.user_id, 
                status='scheduled',
                delivery_status='scheduled'
            ).all()
            for letter in scheduled_letters:
                letter.status = 'cancelled'
                letter.delivery_status = 'cancelled'
                print(f"Cancelled scheduled letter {letter.id}")
        
        # Delete all confirmations for this verification
        DeathVerificationConfirmation.query.filter_by(verification_id=verification.id).delete()
        
        # Set cooldown for all trusted contacts who confirmed
        trusted_contacts = TrustedContact.query.filter_by(user_id=current_user.id, is_confirmed=True).all()
        for contact in trusted_contacts:
            contact.set_death_confirmation_cooldown(7)  # 7 days cooldown
        
        if letters_were_processed:
            flash('Death verification denied. All confirmations have been reset, scheduled deliveries cancelled, and trusted contacts have a 7-day cooldown period.', 'success')
        else:
            flash('Death verification denied. All confirmations have been reset and trusted contacts have a 7-day cooldown period.', 'success')
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while processing your response.', 'error')
        print(f"Error processing death verification response: {str(e)}")
    
    return redirect(url_for('views.home'))


@views.route('/delete-letter', methods=['POST'])
@login_required
def delete_letter():
    letter = json.loads(request.data)
    letterId = letter['letterId']
    letter = Letter.query.get(letterId)
    if letter:
        if letter.user_id == current_user.id:
            # Delete associated media files from S3 and database
            try:
                media_result = s3_media_handler.delete_letter_media(letterId, current_user.id)
                if media_result.json.get('success'):
                    print(f"Deleted {media_result.json.get('deleted_count', 0)} media files for letter {letterId}")
                else:
                    print(f"Warning: Failed to delete some media files: {media_result.json.get('error')}")
            except Exception as e:
                print(f"Error deleting media for letter {letterId}: {str(e)}")
            
            # Delete the letter (cascade will handle database cleanup)
            db.session.delete(letter)
            db.session.commit()

    return jsonify({})

@views.route('/edit-letter', methods=['POST'])
@login_required
def edit_letter():
    if request.is_json:
        letter = request.get_json()
        letterId = letter['letterId']
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.title = letter['title']
            letter.content = letter['content']
            letter.recipient_name = letter['recipient_name']
            letter.recipient_email = letter['recipient_email']
            
            # Handle delay after verification if provided
            if 'delay_option' in letter and letter.delivery_type == 'death_verification':
                delay_option = letter['delay_option']
                if delay_option == 'immediate':
                    letter.delay_after_verification = 0
                elif delay_option == '1_day':
                    letter.delay_after_verification = 1
                elif delay_option == '1_week':
                    letter.delay_after_verification = 7
                elif delay_option == '1_month':
                    letter.delay_after_verification = 30
                elif delay_option == 'custom' and 'custom_delay_days' in letter:
                    custom_days = letter['custom_delay_days']
                    if custom_days and str(custom_days).isdigit():
                        days = int(custom_days)
                        if 1 <= days <= 365:
                            letter.delay_after_verification = days
                        else:
                            return jsonify({'error': 'Custom delay must be between 1 and 365 days'}), 400
                    else:
                        return jsonify({'error': 'Please enter a valid number of days for custom delay'}), 400
            
            db.session.commit()
        return jsonify({})
    else:
        letterId = request.form.get('letterId')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.title = request.form.get('title')
            letter.content = request.form.get('content')
            letter.recipient_name = request.form.get('recipient_name')
            letter.recipient_email = request.form.get('recipient_email')
            
            # Handle delay after verification if provided
            if letter.delivery_type == 'death_verification':
                delay_option = request.form.get('delay_option')
                if delay_option:
                    if delay_option == 'immediate':
                        letter.delay_after_verification = 0
                    elif delay_option == '1_day':
                        letter.delay_after_verification = 1
                    elif delay_option == '1_week':
                        letter.delay_after_verification = 7
                    elif delay_option == '1_month':
                        letter.delay_after_verification = 30
                    elif delay_option == 'custom':
                        custom_days = request.form.get('custom_delay_days')
                        if custom_days and custom_days.isdigit():
                            days = int(custom_days)
                            if 1 <= days <= 365:
                                letter.delay_after_verification = days
                            else:
                                flash('Custom delay must be between 1 and 365 days.', 'error')
                                return redirect(url_for('views.view_letters', user_id=current_user.id))
                        else:
                            flash('Please enter a valid number of days for custom delay.', 'error')
                            return redirect(url_for('views.view_letters', user_id=current_user.id))
            
            db.session.commit()
            flash('Letter updated successfully!', 'success')
        return redirect(url_for('views.view_letters', user_id=current_user.id))

@views.route('/update-letter-status', methods=['POST'])
@login_required
def update_letter_status():
    if request.is_json:
        data = request.get_json()
        letterId = data['letterId']
        new_status = data.get('status')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            letter.status = new_status
            db.session.commit()
            flash('Letter status updated successfully!', category='success')
        else:
            flash('You do not have permission to update this letter!', category='error')
        return jsonify({})
    else:
        letterId = request.form.get('letterId')
        letter = Letter.query.get(letterId)
        if letter and letter.user_id == current_user.id:
            delivery_type = request.form.get('delivery_type')
            letter.delivery_type = delivery_type
            if delivery_type == 'date':
                scheduled_date = request.form.get('scheduled_date')
                if scheduled_date:
                    # Set delivery time to 8 PM (20:00) in user's local timezone
                    letter.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
                    letter.delivery_status = 'pending'
                    letter.status = 'scheduled'
                else:
                    letter.delivery_date = None
                    letter.delivery_status = None
            elif delivery_type == 'death_verification':
                # No longer require trusted contacts for this delivery type
                letter.status = 'pending_verification'
                letter.delivery_date = None
                letter.delivery_status = None
            db.session.commit()
            flash('Delivery type updated successfully!', 'success')
        return redirect(url_for('views.view_letters', user_id=current_user.id))

@views.route('/trusted-contacts', methods=['GET'])
@login_required
def trusted_contacts():
    contacts = TrustedContact.query.filter_by(user_id=current_user.id).all()
    
    # Convert TrustedContact objects to dictionaries for JSON serialization
    contacts_data = []
    for contact in contacts:
        contacts_data.append({
            'id': contact.id,
            'full_name': contact.full_name,
            'email': contact.email,
            'phone': contact.phone,
            'relationship': contact.relationship,
            'is_confirmed': contact.is_confirmed,
            'created_date': contact.created_date.isoformat() if contact.created_date else None
        })
    
    return render_template("trusted_contacts.html", user=current_user, contacts=contacts_data)

@views.route('/add-trusted-contact', methods=['POST'])
@login_required
def add_trusted_contact():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    if not first_name or not last_name or not email:
        flash('First name, last name, and email are required!', category='error')
        return redirect(url_for('views.trusted_contacts'))
    
    # Prevent user from adding themselves as a trusted contact
    if email.lower() == current_user.email.lower():
        flash('You cannot add yourself as a trusted contact!', category='error')
        return redirect(url_for('views.trusted_contacts'))

    full_name = f"{first_name} {last_name}"
    confirmation_code = str(uuid.uuid4())
    new_contact = TrustedContact(
        user_id=current_user.id,
        full_name=full_name,
        email=email,
        phone=phone,
        relationship=relationship,
        confirmation_code=confirmation_code
    )
    db.session.add(new_contact)
    db.session.commit()

    # Send confirmation email
    confirmation_link = url_for('views.confirm_contact', code=confirmation_code, _external=True)
    msg = Message('You\'re Invited to Be a Trusted Contact - LetterForLater',
                  recipients=[email],
                  sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com'))
    
    # Render HTML template
    msg.html = render_template('emails/trusted_contact_invite.html',
        recipient_name=email.split('@')[0],  # Use email prefix as name if not provided
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        sender_email=current_user.email,
        confirmation_link=confirmation_link
    )
    
    # Render text template
    msg.body = render_template('emails/trusted_contact_invite.txt',
        recipient_name=email.split('@')[0],
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        sender_email=current_user.email,
        confirmation_link=confirmation_link
    )
    
    try:
        mail.send(msg)
        flash('Trusted contact added successfully! Confirmation email sent.', category='success')
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        flash('Trusted contact added successfully! Confirmation email will be sent shortly.', category='success')

    # Check if user came from letter form
    from_letter = request.args.get('from_letter')
    if from_letter == '1':
        return redirect(url_for('views.trusted_contacts', from_letter=1))
    return redirect(url_for('views.trusted_contacts'))

@views.route('/confirm-contact/<code>', methods=['GET', 'POST'])
def confirm_contact(code):
    contact = TrustedContact.query.filter_by(confirmation_code=code).first()
    if not contact:
        flash('Invalid confirmation code.', category='error')
        return redirect(url_for('auth.login'))
    if contact.is_confirmed:
        flash('You have already confirmed your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if current_user.is_authenticated and current_user.email == contact.email:
        if request.method == 'POST':
            action = request.form.get('action')
            if action == 'accept':
                contact.is_confirmed = True
                db.session.commit()
                # Promote user to trusted_main if not already
                if current_user.role != 'trusted_main':
                    current_user.role = 'trusted_main'
                    db.session.commit()
                # Ensure DeathVerification record exists for this user if they have at least one letter requiring death verification
                has_pending_letter = Letter.query.filter_by(user_id=contact.user_id, delivery_type='death_verification', status='pending_verification').first()
                if has_pending_letter:
                    dv = DeathVerification.query.filter_by(user_id=contact.user_id, status='pending').first()
                    if not dv:
                        dv = DeathVerification(
                            user_id=contact.user_id,
                            confirmations_count=0,
                            status='pending',
                            verification_code=str(uuid.uuid4())
                        )
                        db.session.add(dv)
                flash('You have accepted the trusted contact request.', category='success')
                db.session.commit()
                return redirect(url_for('views.verify_death'))
            elif action == 'deny':
                db.session.delete(contact)
                db.session.commit()
                flash('You have declined the trusted contact request.', category='info')
            return redirect(url_for('views.home'))
        return render_template('confirm_trusted_contact.html', contact=contact, user=current_user)
    user = User.query.filter_by(email=contact.email).first()
    if user:
        flash('Please log in to confirm your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    session['trusted_contact_code'] = code
    flash('Please sign up to complete the confirmation process.', category='info')
    return redirect(url_for('auth.sign_up'))

@views.route('/resend-confirmation/<int:contact_id>')
@login_required
def resend_confirmation(contact_id):
    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        # Generate new confirmation code if one doesn't exist
        if not contact.confirmation_code:
            contact.confirmation_code = str(uuid.uuid4())
            db.session.commit()
        
        confirmation_link = url_for('views.confirm_contact', code=contact.confirmation_code, _external=True)
        msg = Message('You\'re Invited to Be a Trusted Contact - LetterForLater',
                      recipients=[contact.email],
                      sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com'))
        
        # Render HTML template
        msg.html = render_template('emails/trusted_contact_invite.html',
            recipient_name=contact.email.split('@')[0],
            sender_name=f"{current_user.first_name} {current_user.last_name}",
            sender_email=current_user.email,
            confirmation_link=confirmation_link
        )
        
        # Render text template
        msg.body = render_template('emails/trusted_contact_invite.txt',
            recipient_name=contact.email.split('@')[0],
            sender_name=f"{current_user.first_name} {current_user.last_name}",
            sender_email=current_user.email,
            confirmation_link=confirmation_link
        )
        
        try:
            mail.send(msg)
            flash('Confirmation email resent successfully!', category='success')
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            flash('Confirmation email will be sent shortly.', category='success')
    else:
        flash('You do not have permission to resend confirmation for this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/delete-trusted-contact', methods=['POST'])
@login_required
def delete_trusted_contact():
    contact_id = request.form.get('contact_id')
    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        db.session.delete(contact)
        db.session.commit()
        flash('Trusted contact deleted successfully!', category='success')
    else:
        flash('You do not have permission to delete this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/edit-trusted-contact', methods=['POST'])
@login_required
def edit_trusted_contact():
    contact_id = request.form.get('contact_id')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    contact = TrustedContact.query.get(contact_id)
    if contact and contact.user_id == current_user.id:
        # Prevent user from editing a contact to have their own email
        if email.lower() == current_user.email.lower():
            flash('You cannot set a trusted contact email to your own email address!', category='error')
            return redirect(url_for('views.trusted_contacts'))
        
        contact.full_name = f"{first_name} {last_name}"
        contact.email = email
        contact.phone = phone
        contact.relationship = relationship
        db.session.commit()
        flash('Trusted contact updated successfully!', category='success')
    else:
        flash('You do not have permission to edit this contact!', category='error')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/view-letters/<int:user_id>')
@login_required
def view_letters(user_id):
    # Get status filter from query parameters
    status_filter = request.args.get('status', None)
    
    # Allow main user to view only their own letters
    if current_user.id == user_id:
        letters_query = Letter.query.filter_by(user_id=user_id)
        
        # Apply status filter if provided
        if status_filter:
            letters_query = letters_query.filter_by(status=status_filter)
            
        letters = letters_query.all()
        return render_template('view_letters.html', user=current_user, letters=letters, contact=None, is_owner=True, now=datetime.now(timezone.utc), status_filter=status_filter)
    
    # Otherwise, check if current user is a trusted contact for this user
    contact = TrustedContact.query.filter_by(
        user_id=user_id,
        email=current_user.email
    ).first()
    if not contact or not contact.can_view_letters():
        flash('You do not have permission to view these letters.', category='error')
        return redirect(url_for('views.home'))
    
    letters_query = Letter.query.filter_by(user_id=user_id)
    
    # Apply status filter if provided
    if status_filter:
        letters_query = letters_query.filter_by(status=status_filter)
        
    letters = letters_query.all()
    return render_template('view_letters.html', user=current_user, letters=letters, contact=contact, is_owner=False, now=datetime.now(timezone.utc), status_filter=status_filter)

@views.route('/view-letter/<int:letter_id>')
@login_required
def view_letter(letter_id):
    """View a specific letter by ID"""
    letter = Letter.query.get_or_404(letter_id)
    
    # Check if current user is the owner of the letter
    if current_user.id == letter.user_id:
        return render_template('view_letter.html', letter=letter, is_owner=True)
    
    # Check if current user is a trusted contact for the letter owner
    contact = TrustedContact.query.filter_by(
        user_id=letter.user_id,
        email=current_user.email
    ).first()
    
    if not contact or not contact.can_view_letters():
        flash('You do not have permission to view this letter.', category='error')
        return redirect(url_for('views.home'))
    
    return render_template('view_letter.html', letter=letter, is_owner=False)

@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone = request.form.get('phone', '').strip()
        errors = []
        if len(first_name) < 2:
            errors.append('First name must be at least 2 characters.')
        if len(last_name) < 2:
            errors.append('Last name must be at least 2 characters.')
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('views.settings'))
        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.phone = phone
        db.session.commit()
        flash('Account settings updated successfully!', 'success')
        return redirect(url_for('views.settings'))
    return render_template('settings.html', user=current_user)

@views.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validation
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'error')
        return redirect(url_for('views.settings'))
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('views.settings'))
    
    if len(new_password) < 7:
        flash('New password must be at least 7 characters long.', 'error')
        return redirect(url_for('views.settings'))
    
    # Prevent using the same password
    if current_password == new_password:
        flash('New password must be different from your current password.', 'error')
        return redirect(url_for('views.settings'))
    
    # Verify current password
    if not check_password_hash(current_user.password, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('views.settings'))
    
    # Update password
    try:
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Password changed successfully! Please log in again with your new password.', 'success')
        
        # Log out the user after password change for security
        from flask_login import logout_user
        logout_user()
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while changing your password. Please try again.', 'error')
        print(f"Error changing password: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/change-email', methods=['POST'])
@login_required
def change_email():
    new_email = request.form.get('new_email')
    confirm_email = request.form.get('confirm_new_email')
    current_password = request.form.get('current_password')
    
    # Validation
    if not new_email or not confirm_email or not current_password:
        flash('All fields are required.', 'error')
        return redirect(url_for('views.settings'))
    
    if new_email != confirm_email:
        flash('Email addresses do not match.', 'error')
        return redirect(url_for('views.settings'))
    
    if new_email.lower() == current_user.email.lower():
        flash('New email must be different from your current email.', 'error')
        return redirect(url_for('views.settings'))
    
    # Verify current password
    if not check_password_hash(current_user.password, current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('views.settings'))
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=new_email.lower()).first()
    if existing_user:
        flash('This email address is already in use.', 'error')
        return redirect(url_for('views.settings'))
    
    # Update email
    try:
        current_user.email = new_email.lower()
        db.session.commit()
        flash('Email change request submitted. Please check your new email for verification instructions.', 'success')
        return redirect(url_for('views.settings'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while changing your email. Please try again.', 'error')
        print(f"Error changing email: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    password = request.form.get('password')
    confirmation = request.form.get('confirmation')
    
    # Validation
    if not password or not confirmation:
        flash('All fields are required.', 'error')
        return redirect(url_for('views.settings'))
    
    if confirmation != 'DELETE':
        flash('Please type "DELETE" exactly to confirm account deletion.', 'error')
        return redirect(url_for('views.settings'))
    
    # Verify password
    if not check_password_hash(current_user.password, password):
        flash('Password is incorrect.', 'error')
        return redirect(url_for('views.settings'))
    
    # Delete account and all associated data
    try:
        # Delete all user's letters
        Letter.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all trusted contacts
        TrustedContact.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all notifications
        Notification.query.filter_by(user_id=current_user.id).delete()
        
        # Delete all media attachments
        MediaAttachment.query.filter_by(user_id=current_user.id).delete()
        
        # Delete user account
        db.session.delete(current_user)
        db.session.commit()
        
        flash('Your account has been permanently deleted.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting your account. Please try again.', 'error')
        print(f"Error deleting account: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/logout-all-devices', methods=['POST'])
@login_required
def logout_all_devices():
    try:
        # In a real implementation, you would invalidate all user sessions
        # For now, we'll just log out the current user
        from flask_login import logout_user
        logout_user()
        flash('You have been logged out of all devices.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        flash('An error occurred while logging out devices. Please try again.', 'error')
        print(f"Error logging out devices: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/request-data-export', methods=['POST'])
@login_required
def request_data_export():
    try:
        # In a real implementation, you would queue a background task to export user data
        # For now, we'll just show a success message
        flash('Your data export request has been submitted. You will receive an email with download instructions within 24 hours.', 'success')
        return redirect(url_for('views.settings'))
        
    except Exception as e:
        flash('An error occurred while requesting data export. Please try again.', 'error')
        print(f"Error requesting data export: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/request-data-deletion', methods=['POST'])
@login_required
def request_data_deletion():
    password = request.form.get('password')
    confirmation = request.form.get('confirmation')
    
    # Validation
    if not password or not confirmation:
        flash('All fields are required.', 'error')
        return redirect(url_for('views.settings'))
    
    if confirmation != 'DELETE MY DATA':
        flash('Please type "DELETE MY DATA" exactly to confirm data deletion.', 'error')
        return redirect(url_for('views.settings'))
    
    # Verify password
    if not check_password_hash(current_user.password, password):
        flash('Password is incorrect.', 'error')
        return redirect(url_for('views.settings'))
    
    try:
        # In a real implementation, you would queue a background task to delete user data
        # For now, we'll just show a success message
        flash('Your data deletion request has been submitted. Your data will be permanently deleted within 30 days.', 'success')
        return redirect(url_for('views.settings'))
        
    except Exception as e:
        flash('An error occurred while requesting data deletion. Please try again.', 'error')
        print(f"Error requesting data deletion: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/update-notification-preferences', methods=['POST'])
@login_required
def update_notification_preferences():
    try:
        # Get notification preferences from form
        product_updates = request.form.get('product_updates') == 'true'
        marketing_emails = request.form.get('marketing_emails') == 'true'
        
        # Update user's notification preferences
        current_user.notification_preferences = {
            'email_notifications': True,  # Always enabled for security
            'product_updates': product_updates,
            'marketing_emails': marketing_emails
        }
        
        db.session.commit()
        flash('Notification preferences updated successfully!', 'success')
        return redirect(url_for('views.settings'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating notification preferences. Please try again.', 'error')
        print(f"Error updating notification preferences: {str(e)}")
        return redirect(url_for('views.settings'))

@views.route('/save-draft', methods=['POST'])
@login_required
def save_draft():
    data = request.get_json()
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    recipient_name = data.get('recipient_name', '').strip()
    recipient_email = data.get('recipient_email', '').strip()
    delivery_type = data.get('delivery_type')
    scheduled_date = data.get('scheduled_date')
    media_files = data.get('media_files', [])  # Get media files from frontend
    
    # Process media files for draft

    # Save draft even with minimal content to preserve user work
    # Only skip if literally nothing is provided (including media files)
    if not any([title, content, recipient_name, recipient_email, delivery_type]) and len(media_files) == 0:
        return jsonify({'success': False, 'reason': 'empty', 'draft_id': None})

    # For draft auto-save, don't consider letters "complete" and delete drafts
    # Only delete drafts when the user actually submits the form
    # This prevents losing work when navigating away to add trusted contacts
    
    # We'll keep all drafts until the user actually submits the form

    # Otherwise, update or create the draft as before
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').order_by(Letter.last_modified.desc()).first()
    if draft:
        # Update the existing draft
        draft.title = title or ''
        draft.content = content or ''
        draft.recipient_name = recipient_name or ''
        draft.recipient_email = recipient_email or ''
        draft.delivery_type = delivery_type or 'date'
        draft.last_modified = datetime.now(timezone.utc)
        
        # Handle media files - attach them to the draft
        if media_files:
            try:
                media_ids = [media_info.get('media_id') for media_info in media_files if media_info.get('media_id')]
                if media_ids:
                    result = production_media_handlers.media_handler.attach_media_to_letter(
                        current_user.id,
                        draft.id,
                        media_ids
                    )
                    if not result.json.get('success'):
                        print(f"Warning: Failed to attach some media files to draft {draft.id}: {result.json.get('error')}")
            except Exception as e:
                print(f"Error processing media attachments during draft save: {e}")
        
        db.session.commit()
        # Update or create delivery schedule if needed
        if delivery_type == 'date' and scheduled_date:
            # Set delivery time to 8 PM (20:00) in user's local timezone
            draft.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
            draft.delivery_status = 'pending'
        elif delivery_type != 'date' and draft.delivery_date:
            draft.delivery_date = None
            draft.delivery_status = None
        return jsonify({'success': True, 'draft_id': draft.id, 'updated': True})
    else:
        # Create a new draft
        draft = Letter(
            title=title or '',
            content=content or '',
            recipient_name=recipient_name or '',
            recipient_email=recipient_email or '',
            delivery_type=delivery_type or 'date',
            status='draft',
            user_id=current_user.id
        )
        db.session.add(draft)
        db.session.commit()
        
        # Handle media files - attach them to the new draft
        if media_files:
            try:
                media_ids = [media_info.get('media_id') for media_info in media_files if media_info.get('media_id')]
                if media_ids:
                    result = production_media_handlers.media_handler.attach_media_to_letter(
                        current_user.id,
                        draft.id,
                        media_ids
                    )
                    if not result.json.get('success'):
                        print(f"Warning: Failed to attach some media files to new draft {draft.id}: {result.json.get('error')}")
            except Exception as e:
                print(f"Error processing media attachments during new draft creation: {e}")
        
        # Save scheduled date if present
        if delivery_type == 'date' and scheduled_date:
            # Set delivery time to 8 PM (20:00) in user's local timezone
            draft.delivery_date = datetime.strptime(scheduled_date, '%Y-%m-%d').replace(hour=20, minute=0, second=0)
            draft.delivery_status = 'pending'
        return jsonify({'success': True, 'draft_id': draft.id, 'created': True})

@views.route('/get-draft', methods=['GET'])
@login_required
def get_draft():
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').order_by(Letter.last_modified.desc()).first()
    if not draft:
        return jsonify({'draft': None})
    # Load media files from the database table (new system)
    media_attachments = MediaAttachment.query.filter_by(letter_id=draft.id, user_id=current_user.id).all()
    media_files = []
    for attachment in media_attachments:
        media_files.append({
            'id': attachment.id,
            'name': attachment.file_name,
            'size': attachment.file_size,
            'type': attachment.mime_type,
            'file_type': attachment.file_type,
            'media_id': attachment.id  # For serving media
        })
    
    draft_data = {
        'letter_id': draft.id,  # Include the actual letter ID
        'title': draft.title,
        'content': draft.content,
        'recipient_name': draft.recipient_name,
        'recipient_email': draft.recipient_email,
        'delivery_type': draft.delivery_type,
        'scheduled_date': draft.delivery_date.strftime('%Y-%m-%d') if draft.delivery_date else '',
        'media_files': media_files  # Include media files from database
    }
    
    # Return draft data with media files
    
    return jsonify({'draft': draft_data})

@views.route('/delete-draft', methods=['POST'])
@login_required
def delete_draft():
    draft = Letter.query.filter_by(user_id=current_user.id, status='draft').first()
    if draft:
        db.session.delete(draft)
        db.session.commit()
    return jsonify({'success': True})

@views.route('/invite-trusted-contact', methods=['POST'])
@login_required
def invite_trusted_contact():
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    relationship = request.form.get('relationship')

    if not first_name or not last_name or not email:
        flash('First name, last name, and email are required!', category='error')
        return redirect(url_for('views.trusted_contacts'))
    
    # Prevent user from adding themselves as a trusted contact
    if email.lower() == current_user.email.lower():
        flash('You cannot add yourself as a trusted contact!', category='error')
        return redirect(url_for('views.trusted_contacts'))

    # Check for existing invite
    existing = TrustedContact.query.filter_by(user_id=current_user.id, email=email).first()
    if existing:
        # Resend confirmation email
        if not existing.confirmation_code:
            existing.confirmation_code = str(uuid.uuid4())
            db.session.commit()
        confirmation_link = url_for('views.confirm_trust', token=existing.confirmation_code, _external=True)
        msg = Message('You\'re Invited to Be a Trusted Contact - LetterForLater', 
                      recipients=[email],
                      sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com'))
        
        # Render HTML template
        msg.html = render_template('emails/trusted_contact_invite.html',
            recipient_name=email.split('@')[0],
            sender_name=f"{current_user.first_name} {current_user.last_name}",
            sender_email=current_user.email,
            confirmation_link=confirmation_link
        )
        
        # Render text template
        msg.body = render_template('emails/trusted_contact_invite.txt',
            recipient_name=email.split('@')[0],
            sender_name=f"{current_user.first_name} {current_user.last_name}",
            sender_email=current_user.email,
            confirmation_link=confirmation_link
        )
        
        try:
            mail.send(msg)
            flash('Confirmation email resent successfully!', category='success')
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            flash('Confirmation email will be sent shortly.', category='success')
        return redirect(url_for('views.trusted_contacts'))

    # Create new invite
    confirmation_code = str(uuid.uuid4())
    new_contact = TrustedContact(
        user_id=current_user.id,
        full_name=f"{first_name} {last_name}",
        email=email,
        phone=phone,
        relationship=relationship,
        confirmation_code=confirmation_code
    )
    db.session.add(new_contact)
    db.session.commit()
    confirmation_link = url_for('views.confirm_trust', token=confirmation_code, _external=True)
    msg = Message('You\'re Invited to Be a Trusted Contact - LetterForLater', 
                  recipients=[email],
                  sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com'))
    
    # Render HTML template
    msg.html = render_template('emails/trusted_contact_invite.html',
        recipient_name=email.split('@')[0],
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        sender_email=current_user.email,
        confirmation_link=confirmation_link
    )
    
    # Render text template
    msg.body = render_template('emails/trusted_contact_invite.txt',
        recipient_name=email.split('@')[0],
        sender_name=f"{current_user.first_name} {current_user.last_name}",
        sender_email=current_user.email,
        confirmation_link=confirmation_link
    )
    
    try:
        mail.send(msg)
        flash('Trusted contact invited successfully! Confirmation email sent.', category='success')
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        flash('Trusted contact invited successfully! Confirmation email will be sent shortly.', category='success')
    return redirect(url_for('views.trusted_contacts'))

@views.route('/confirm-trust', methods=['GET', 'POST'])
def confirm_trust():
    token = request.args.get('token')
    contact = TrustedContact.query.filter_by(confirmation_code=token).first()
    if not contact:
        flash('Invalid or expired confirmation token.', category='error')
        return redirect(url_for('auth.login'))
    if contact.is_confirmed:
        flash('You have already confirmed your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if not current_user.is_authenticated:
        session['trusted_contact_code'] = token
        flash('Please log in to confirm your trusted contact role.', category='info')
        return redirect(url_for('auth.login'))
    if current_user.email != contact.email:
        flash('You were not invited with this email.', category='error')
        return redirect(url_for('views.home'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'accept':
            contact.is_confirmed = True
            db.session.commit()
            # Promote user to trusted_main if not already
            if current_user.role != 'trusted_main':
                current_user.role = 'trusted_main'
                db.session.commit()
            flash('You have accepted the trusted contact request.', category='success')
            return redirect(url_for('views.verify_death'))
        elif action == 'deny':
            db.session.delete(contact)
            db.session.commit()
            flash('You have declined the trusted contact request.', category='info')
        return redirect(url_for('views.home'))
    return render_template('confirm_trusted_contact.html', contact=contact, user=current_user)

@views.route('/pending-trusted-contact/<int:invite_id>', methods=['GET', 'POST'])
@login_required
def pending_trusted_contact(invite_id):
    from website.models import TrustedContact
    contact = TrustedContact.query.get(invite_id)
    if not contact or contact.email != current_user.email or contact.is_confirmed:
        flash('Invalid or expired trusted contact invitation.', 'error')
        return redirect(url_for('views.home'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'accept':
            contact.is_confirmed = True
            if current_user.role != 'trusted_main':
                current_user.role = 'trusted_main'
            db.session.commit()
            flash('You have accepted the trusted contact request.', 'success')
        elif action == 'decline':
            db.session.delete(contact)
            db.session.commit()
            flash('You have declined the trusted contact request.', 'info')
        return redirect(url_for('views.home'))
    return render_template('pending_trusted_contact.html', contact=contact, user=current_user)

@views.route('/api/trusted-contacts-status')
@login_required
def api_trusted_contacts_status():
    """Check if user has confirmed trusted contacts"""
    confirmed_contacts = TrustedContact.query.filter_by(
        user_id=current_user.id, 
        is_confirmed=True
    ).count()
    
    return jsonify({
        'has_confirmed_contacts': confirmed_contacts > 0,
        'confirmed_count': confirmed_contacts
    })

@views.route('/api/notifications')
@login_required
def api_notifications():
    from website.models import TrustedContact, Notification
    
    # Get pending trusted contact invitations
    invitations = TrustedContact.query.filter_by(email=current_user.email, is_confirmed=False).all()
    invitation_data = [
        {
            'id': invite.id,
            'type': 'trusted_contact_invitation',
            'from_name': invite.user.first_name + ' ' + invite.user.last_name,
            'from_email': invite.user.email,
            'contact_id': invite.id,
            'confirmation_code': invite.confirmation_code
        }
        for invite in invitations
    ]
    
    # Get unread notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    notification_data = []
    for notif in notifications:
        notification_item = {
            'id': notif.id,
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'created_at': notif.created_at.isoformat(),
            'related_trusted_contact_id': notif.related_trusted_contact_id
        }
        
        # Add specific data for death verification confirmations
        if notif.notification_type == 'death_verification_confirmation' and notif.related_trusted_contact_id:
            trusted_contact = TrustedContact.query.get(notif.related_trusted_contact_id)
            if trusted_contact:
                notification_item['trusted_contact_name'] = trusted_contact.full_name
                notification_item['trusted_contact_id'] = trusted_contact.id
        
        notification_data.append(notification_item)
    
    # Combine both types of notifications
    all_notifications = invitation_data + notification_data
    
    return jsonify({
        'notifications': all_notifications,
        'pending_trusted_invitations': invitation_data
    })

@views.route('/api/remove-invitation/<int:invite_id>', methods=['POST'])
@login_required
def api_remove_invitation(invite_id):
    from website.models import TrustedContact
    invite = TrustedContact.query.get(invite_id)
    if invite and invite.email == current_user.email and not invite.is_confirmed:
        db.session.delete(invite)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403

@views.route('/api/mark-notification-read/<int:notification_id>', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """Mark a notification as read"""
    from website.models import Notification
    notification = Notification.query.get(notification_id)
    if notification and notification.user_id == current_user.id:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 403

@views.route('/api/reject-death-confirmation', methods=['POST'])
@login_required
def api_reject_death_confirmation():
    """Allow main user to reject a death confirmation"""
    from website.models import Notification, DeathVerification, DeathVerificationConfirmation
    data = request.get_json()
    notification_id = data.get('notification_id')
    trusted_contact_id = data.get('trusted_contact_id')
    
    if not notification_id or not trusted_contact_id:
        return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
    
    # Verify the notification belongs to current user
    notification = Notification.query.get(notification_id)
    if not notification or notification.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Invalid notification'}), 403
    
    # Find the death verification confirmation to reject
    trusted_contact = TrustedContact.query.get(trusted_contact_id)
    if not trusted_contact or trusted_contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Invalid trusted contact'}), 403
    
    # Find the death verification record
    death_verification = DeathVerification.query.filter_by(user_id=current_user.id).first()
    if not death_verification:
        return jsonify({'success': False, 'error': 'No death verification found'}), 404
    
    # Find the specific confirmation to reject
    confirmation = DeathVerificationConfirmation.query.filter_by(
        verification_id=death_verification.id,
        trusted_contact_id=trusted_contact_id,
        confirmed=True
    ).first()
    
    if not confirmation:
        return jsonify({'success': False, 'error': 'No confirmation found to reject'}), 404
    
    try:
        # Remove the confirmation
        db.session.delete(confirmation)
        
        # Update the death verification count
        death_verification.confirmations_count = max(0, death_verification.confirmations_count - 1)
        
        # Set 7-day cooldown for the trusted contact
        trusted_contact.set_death_confirmation_cooldown(7)
        
        # Mark the notification as read
        notification.is_read = True
        
        # Create a new notification for the main user about the cooldown
        cooldown_notification = create_notification(
            user_id=current_user.id,
            notification_type='death_verification_cooldown',
            title=f'Trusted Contact in Cooldown: {trusted_contact.full_name}',
            message=f'This trusted contact is now in a 7-day cooldown period and cannot confirm your death again.',
            related_trusted_contact_id=trusted_contact_id
        )
        
        # Send email to the trusted contact who made the confirmation
        try:
            msg = Message(
                'Death Confirmation Rejected - LetterForLater',
                recipients=[trusted_contact.email],
                sender=os.getenv('MAIL_USERNAME', 'support@letterforlater.com')
            )
            
            # For now, use a simple text email since we don't have a specific template for this
            msg.body = f"""
Dear {trusted_contact.full_name},

Your death confirmation for {current_user.first_name} {current_user.last_name} has been rejected.

This means the person is still alive and has logged into their LetterForLater account to reject your confirmation.

Please verify the person's status before submitting another death confirmation.

Best regards,
LetterForLater Team
"""
            mail.send(msg)
        except Exception as e:
            print(f"Error sending rejection email: {str(e)}")
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Death confirmation rejected successfully'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error rejecting death confirmation: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to reject confirmation'}), 500

@views.route('/api/handle-invitation', methods=['POST'])
@login_required
def api_handle_invitation():
    """Handle trusted contact invitation (accept or deny)"""
    from website.models import Notification, TrustedContact
    data = request.get_json()
    notification_id = data.get('notification_id')
    action = data.get('action')
    
    if not notification_id or not action:
        return jsonify({'success': False, 'error': 'Missing required parameters'}), 400
    
    # First try to find it as a TrustedContact invitation
    trusted_contact = TrustedContact.query.get(notification_id)
    if trusted_contact and trusted_contact.email == current_user.email and not trusted_contact.is_confirmed:
        # This is a trusted contact invitation
        try:
            if action == 'accept':
                # Confirm the trusted contact
                trusted_contact.is_confirmed = True
                
                # Promote user to trusted_main if not already
                if current_user.role != 'trusted_main':
                    current_user.role = 'trusted_main'
                
                # Create success notification for the inviter
                create_notification(
                    user_id=trusted_contact.user_id,
                    notification_type='trusted_contact_confirmed',
                    title=f'Trusted Contact Confirmed: {current_user.first_name} {current_user.last_name}',
                    message=f'{current_user.first_name} {current_user.last_name} has accepted your trusted contact invitation.',
                    related_trusted_contact_id=trusted_contact.id
                )
                
                db.session.commit()
                return jsonify({'success': True, 'message': 'Invitation accepted successfully'})
                
            elif action == 'deny':
                # Delete the trusted contact invitation
                db.session.delete(trusted_contact)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Invitation declined'})
                
        except Exception as e:
            db.session.rollback()
            print(f"Error handling trusted contact invitation: {str(e)}")
            return jsonify({'success': False, 'error': 'Failed to handle invitation'}), 500
    
    # If not found as TrustedContact, return error
    return jsonify({'success': False, 'error': 'Invalid notification'}), 403

@views.route('/api/remove-trusted-contact/<int:contact_id>', methods=['POST'])
@login_required
def api_remove_trusted_contact(contact_id):
    """Remove a trusted contact"""
    from website.models import TrustedContact
    contact = TrustedContact.query.get(contact_id)
    if not contact or contact.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Contact not found or access denied'}), 403
    
    try:
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Trusted contact removed successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error removing trusted contact: {str(e)}")
        return jsonify({'success': False, 'error': 'Failed to remove contact'}), 500

@views.route('/send-scheduled-letters', methods=['POST'])
@login_required
def send_scheduled_letters():
    """Send letters that are scheduled for delivery after death verification delay"""
    if current_user.role != 'admin':  # Only admins can trigger this
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    # Find letters that are scheduled and past their delivery date
    now = datetime.now(timezone.utc)
    scheduled_letters = Letter.query.filter(
        Letter.status == 'scheduled',
        Letter.delivery_status.in_(['scheduled', 'pending']),
        Letter.delivery_date <= now
    ).all()
    
    sent_count = 0
    for letter in scheduled_letters:
        try:
            success = send_letter_with_media(
                letter, 
                letter.recipient_email, 
                letter.recipient_name, 
                f"{letter.author.first_name} {letter.author.last_name}"
            )
            if success:
                letter.status = 'delivered'
                letter.delivery_status = 'delivered'
                sent_count += 1
                print(f"Scheduled letter {letter.id} sent with media to {letter.recipient_email}")
            else:
                print(f"Failed to send scheduled letter {letter.id} to {letter.recipient_email}")
        except Exception as e:
            print(f"Error sending scheduled letter {letter.id} to {letter.recipient_email}: {str(e)}")
            # Keep the letter as scheduled if there's an error
    
    try:
        db.session.commit()
        return jsonify({'success': True, 'sent_count': sent_count})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def send_scheduled_letters_task():
    """Background task to send scheduled letters - can be called by cron job"""
    from flask import current_app
    with current_app.app_context():
        now = datetime.now(timezone.utc)
        scheduled_letters = Letter.query.filter(
            Letter.status == 'scheduled',
            Letter.delivery_status.in_(['scheduled', 'pending']),
            Letter.delivery_date <= now
        ).all()
        
        for letter in scheduled_letters:
            try:
                success = send_letter_with_media(
                    letter, 
                    letter.recipient_email, 
                    letter.recipient_name, 
                    f"{letter.author.first_name} {letter.author.last_name}"
                )
                if success:
                    letter.status = 'delivered'
                    letter.delivery_status = 'delivered'
                    print(f"Sent scheduled letter {letter.id} with media to {letter.recipient_email}")
                else:
                    print(f"Failed to send scheduled letter {letter.id} to {letter.recipient_email}")
            except Exception as e:
                print(f"Error sending scheduled letter {letter.id}: {str(e)}")
        
        try:
            db.session.commit()
            print(f"Processed {len(scheduled_letters)} scheduled letters")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing scheduled letter updates: {str(e)}")

@views.route('/track-email-open/<token>')
def track_email_open(token):
    """Track when an invite email is opened"""
    try:
        from website.models import RecipientInvite
        
        invite = RecipientInvite.query.filter_by(invite_token=token).first()
        if invite and not invite.opened_at:
            invite.opened_at = datetime.now(timezone.utc)
            db.session.commit()
            print(f"Email opened for invite {invite.id}")
        
        # Return a 1x1 transparent pixel
        from flask import Response
        pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(pixel, mimetype='image/png')
        
    except Exception as e:
        print(f"Error tracking email open: {str(e)}")
        # Still return pixel even if tracking fails
        pixel = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        return Response(pixel, mimetype='image/png')

@views.route('/track-link-click/<token>')
def track_link_click(token):
    """Track when an invite link is clicked"""
    try:
        from website.models import RecipientInvite
        
        invite = RecipientInvite.query.filter_by(invite_token=token).first()
        if invite and not invite.clicked_at:
            invite.clicked_at = datetime.now(timezone.utc)
            db.session.commit()
            print(f"Link clicked for invite {invite.id}")
        
        # Redirect to signup with invite
        return redirect(url_for('auth.sign_up_with_invite', token=token))
        
    except Exception as e:
        print(f"Error tracking link click: {str(e)}")
        return redirect(url_for('auth.sign_up'))

@views.route('/received-letters')
@login_required
def received_letters():
    """Dashboard for recipients to view letters they've received"""
    from website.models import RecipientInvite
    
    # Get all letters this user has received
    received_invites = RecipientInvite.query.filter(
        RecipientInvite.recipient_user_id == current_user.id,
        RecipientInvite.registered_at.isnot(None)
    ).all()
    
    return render_template('received_letters.html', received_invites=received_invites)

@views.route('/view-received-letter/<int:letter_id>')
@login_required
def view_received_letter(letter_id):
    """View a specific received letter"""
    from website.models import RecipientInvite
    
    # Verify the user has access to this letter
    invite = RecipientInvite.query.filter(
        RecipientInvite.letter_id == letter_id,
        RecipientInvite.recipient_user_id == current_user.id,
        RecipientInvite.registered_at.isnot(None)
    ).first()
    
    if not invite:
        flash('You do not have access to this letter.', 'error')
        return redirect(url_for('views.received_letters'))
    
    letter = invite.letter
    
    # Get media attachments for this letter from the MediaAttachment table
    media_attachments = letter.media_files.all()
    
    return render_template('view_received_letter.html', letter=letter, media_attachments=media_attachments)

# ===== PRODUCTION MEDIA SYSTEM =====

from .s3_media_handler import s3_media_handler

@views.route('/create-draft-letter', methods=['POST'])
@login_required
def create_draft_letter():
    """Create a draft letter for media uploads"""
    try:
        # Create a draft letter
        draft_letter = Letter(
            title='',
            content='',
            recipient_name='',
            recipient_email='',
            delivery_type='date',
            status='draft',
            user_id=current_user.id
        )
        db.session.add(draft_letter)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'letter_id': draft_letter.id,
            'message': 'Draft letter created for media uploads'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Failed to create draft letter'}), 500

@views.route('/upload-media-url', methods=['POST'])
@login_required
def generate_upload_url():
    """Generate presigned URL for S3 upload - requires letter_id"""
    data = request.get_json()
    filename = data.get('filename')
    media_type = data.get('media_type', 'image')
    letter_id = data.get('letter_id')  # Required for permanent storage
    
    if not filename:
        return jsonify({'success': False, 'error': 'Filename required'}), 400
    
    if not letter_id:
        return jsonify({'success': False, 'error': 'Letter ID required for media upload'}), 400
    
    # Verify the letter belongs to the current user
    letter = Letter.query.filter_by(id=letter_id, user_id=current_user.id).first()
    if not letter:
        return jsonify({'success': False, 'error': 'Letter not found or access denied'}), 404
    
    return s3_media_handler.generate_upload_url(current_user.id, filename, media_type, letter_id)

@views.route('/confirm-upload', methods=['POST'])
@login_required
def confirm_upload():
    """Confirm successful S3 upload"""
    data = request.get_json()
    media_id = data.get('media_id')
    file_size = data.get('file_size')
    
    if not media_id or not file_size:
        return jsonify({'success': False, 'error': 'Media ID and file size required'}), 400
    
    return s3_media_handler.confirm_upload(media_id, current_user.id, file_size)

@views.route('/media/<int:media_id>/download')
@login_required
def get_media_download_url(media_id):
    """Get presigned download URL for media"""
    return s3_media_handler.generate_download_url(media_id, current_user.id)

@views.route('/media/<int:media_id>')
@login_required
def serve_media(media_id):
    """Serve media files - redirects to S3 presigned URL for viewing"""
    from .models import MediaAttachment, RecipientInvite
    
    # First check if user owns the media
    media = MediaAttachment.query.filter_by(id=media_id, user_id=current_user.id).first()
    
    # If not owned by user, check if they have access as a recipient
    if not media:
        # Check if user is a recipient of a letter containing this media
        media = MediaAttachment.query.get(media_id)
        if media:
            # Check if current user is a recipient of the letter containing this media
            recipient_access = RecipientInvite.query.filter(
                RecipientInvite.letter_id == media.letter_id,
                RecipientInvite.recipient_user_id == current_user.id,
                RecipientInvite.registered_at.isnot(None)
            ).first()
            
            if not recipient_access:
                media = None  # No access
    
    if not media:
        return jsonify({'error': 'Media not found or access denied'}), 404
    
    # Generate presigned URL and redirect
    download_response, status_code = s3_media_handler.generate_download_url(media_id, current_user.id)
    if status_code == 200:  # Success
        import json
        data = json.loads(download_response.get_data(as_text=True))
        return redirect(data['download_url'])
    else:
        return download_response, status_code

@views.route('/download-media/<int:media_id>')
@login_required
def download_media(media_id):
    """Download media files - forces download instead of viewing"""
    from .models import MediaAttachment, RecipientInvite
    import requests
    from flask import Response
    
    # First check if user owns the media
    media = MediaAttachment.query.filter_by(id=media_id, user_id=current_user.id).first()
    
    # If not owned by user, check if they have access as a recipient
    if not media:
        # Check if user is a recipient of a letter containing this media
        media = MediaAttachment.query.get(media_id)
        if media:
            # Check if current user is a recipient of the letter containing this media
            recipient_access = RecipientInvite.query.filter(
                RecipientInvite.letter_id == media.letter_id,
                RecipientInvite.recipient_user_id == current_user.id,
                RecipientInvite.registered_at.isnot(None)
            ).first()
            
            if not recipient_access:
                media = None  # No access
    
    if not media:
        return jsonify({'error': 'Media not found or access denied'}), 404
    
    # Generate presigned URL
    download_response, status_code = s3_media_handler.generate_download_url(media_id, current_user.id)
    if status_code == 200:  # Success
        import json
        data = json.loads(download_response.get_data(as_text=True))
        s3_url = data['download_url']
        
        # Fetch the file from S3
        try:
            response = requests.get(s3_url, stream=True)
            response.raise_for_status()
            
            # Create Flask response with proper headers for download
            def generate():
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            flask_response = Response(
                generate(),
                mimetype=media.mime_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{media.file_name}"',
                    'Content-Length': str(response.headers.get('content-length', '')),
                    'Cache-Control': 'no-cache'
                }
            )
            return flask_response
            
        except Exception as e:
            print(f"Error downloading file from S3: {str(e)}")
            return jsonify({'error': 'Failed to download file'}), 500
    else:
        return download_response, status_code

@views.route('/delete-media/<int:media_id>', methods=['POST'])
@login_required
def delete_media(media_id):
    """Delete a media attachment"""
    return s3_media_handler.delete_media(media_id, current_user.id)

@views.route('/delete-media-session', methods=['POST'])
@login_required
def delete_media_session():
    """Delete media file from S3 and database record"""
    data = request.get_json()
    media_id = data.get('media_id')
    if not media_id:
        return jsonify({'success': False, 'error': 'Media ID required'}), 400
    
    # Use the S3 media handler to properly delete from S3
    return s3_media_handler.delete_media(media_id, current_user.id)

@views.route('/media-session/<media_id>')
@login_required
def serve_media_session(media_id):
    """Serve temporary media files from database"""
    return production_media_handlers.media_handler.serve_media(media_id, current_user.id)

@views.route('/download-media-session/<media_id>')
@login_required
def download_media_session(media_id):
    """Download temporary media files from database"""
    try:
        media = MediaAttachment.query.get_or_404(media_id)
        
        # Check access control
        if media.user_id != current_user.id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Generate download filename
        file_ext = media.file_path.split('.')[-1]
        if media.file_type == 'audio':
            download_name = f"audio_recording_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.{file_ext}"
        elif media.file_type == 'video':
            download_name = f"video_recording_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.{file_ext}"
        else:
            download_name = f"media_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.{file_ext}"
        
        return send_file(
            media.file_path, 
            mimetype=media.mime_type,
            as_attachment=True,
            download_name=download_name
        )
        
    except Exception as e:
        print(f"❌ Error downloading media: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Debug route removed for production

@views.route('/media-stats')
@login_required
def media_stats():
    """Get current user's media statistics"""
    stats = production_media_handlers.media_handler.get_user_media_stats(current_user.id)
    if stats:
        return jsonify(stats)
    else:
        return jsonify({'error': 'Failed to get media stats'}), 500

@views.route('/cleanup-expired-media', methods=['POST'])
@login_required
def cleanup_expired_media():
    """Clean up expired temporary media (admin only)"""
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    cleaned_count = production_media_handlers.media_handler.cleanup_expired_media()
    return jsonify({
        'success': True,
        'cleaned_count': cleaned_count,
        'message': f'Cleaned up {cleaned_count} expired media files'
    })

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', 'your-google-client-id.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', 'your-google-client-secret')

@views.route('/auth/google')
def google_auth():
    """Initiate Google OAuth flow"""
    from flask import current_app
    
    # Check if Google OAuth is properly configured
    if GOOGLE_CLIENT_ID == "your-google-client-id.apps.googleusercontent.com":
        flash('Google Sign-In is not configured yet. Please set up Google OAuth credentials.', 'error')
        return redirect(url_for('auth.login'))
    
    # For development, we'll use a simple redirect to Google's OAuth
    # In production, you'd want to use proper OAuth flow with state parameter
    # Use localhost instead of 127.0.0.1 for consistency
    base_url = request.url_root
    if '127.0.0.1' in base_url:
        base_url = base_url.replace('127.0.0.1', 'localhost')
    redirect_uri = f"{base_url}auth/google/callback"
    google_oauth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=openid email profile&"
        f"response_type=code&"
        f"access_type=offline"
    )
    
    print(f"🔍 Redirect URI: {redirect_uri}")
    print(f"🔍 Google OAuth URL: {google_oauth_url}")
    
    return redirect(google_oauth_url)

@views.route('/auth/google/test')
def google_test():
    """Test route to verify callback URL works"""
    return "Google callback URL is working! 🎉"

@views.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    from flask import current_app
    
    print("🚀 Google callback route hit!")
    
    # Get the authorization code from Google
    code = request.args.get('code')
    print(f"🔍 Google callback received code: {code[:20] if code else 'None'}...")
    
    if not code:
        print("❌ No authorization code received")
        flash('Google authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    
    try:
        # Exchange code for token
        token_url = "https://oauth2.googleapis.com/token"
        # Use localhost instead of 127.0.0.1 for consistency
        base_url = request.url_root
        if '127.0.0.1' in base_url:
            base_url = base_url.replace('127.0.0.1', 'localhost')
        token_data = {
            'client_id': GOOGLE_CLIENT_ID,
            'client_secret': GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': f"{base_url}auth/google/callback"
        }
        
        token_response = http_requests.post(token_url, data=token_data)
        token_json = token_response.json()
        print(f"🔍 Token response: {token_json}")
        
        if 'access_token' not in token_json:
            print(f"❌ No access token in response: {token_json}")
            flash('Failed to get access token from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        # Get user info from Google
        user_info_url = f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={token_json['access_token']}"
        user_info_response = http_requests.get(user_info_url)
        user_info = user_info_response.json()
        print(f"🔍 User info: {user_info}")
        
        if 'email' not in user_info:
            print(f"❌ No email in user info: {user_info}")
            flash('Failed to get user information from Google.', 'error')
            return redirect(url_for('auth.login'))
        
        # Extract user information
        google_id = user_info.get('id')
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        profile_picture = user_info.get('picture', '')
        
        # Check if user already exists
        user = User.query.filter_by(email=email).first()
        
        if user:
            # User exists, update Google info if needed
            if not user.is_google_user:
                user.google_id = google_id
                user.profile_picture = profile_picture
                user.is_google_user = True
                db.session.commit()
        else:
            # Create new user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                google_id=google_id,
                profile_picture=profile_picture,
                is_google_user=True,
                password=None  # No password for Google users
            )
            db.session.add(user)
            db.session.commit()
            
            # Send welcome email for new Google users
            try:
                from .email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                print(f"Error sending welcome email to Google user: {str(e)}")
        
        # Log the user in
        login_user(user, remember=True)
        print(f"✅ User {user.email} logged in successfully with Google")
        
        flash('Successfully signed in with Google!', 'success')
        return redirect(url_for('views.home'))
        
    except Exception as e:
        print(f"❌ Google OAuth error: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Google authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))









