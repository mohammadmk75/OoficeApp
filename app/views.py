from flask import Blueprint, render_template, redirect, url_for, flash, request,jsonify, send_from_directory,current_app,make_response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from app import db, mail, limiter,scheduler
from app.forms import LoginForm, RegistrationForm, ProfileForm,SendInviteForm
from app.models import Users,Tasks,Meetings,Requests,RequestReplies,StickyNotes,Announcements,LunchOrder,TaskLog
from datetime import datetime,timedelta
from flask import jsonify
import pytz
from sqlalchemy import or_,and_
import os
import logging
from app import db
# import time
import pika
import json

def iran_now():
    return datetime.utcnow() + timedelta(hours=3, minutes=30)
now1 = iran_now()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

LUNCH_MENU = {
    "Saturday": ["زرشک پلو (سینه)", "زرشک پلو (ران)", "خوراک مرغ (سینه)", "خوراک مرغ (ران)"],
    "Sunday": ["کوبیده", "جوجه (سینه)", "جوجه (ران)"],
    "Monday": ["عدس پلو", "جوجه (سینه)", "جوجه (ران)"],
    "Tuesday": ["لوبیا پلو", "زرشک پلو (سینه)", "زرشک پلو (ران)", "خوراک مرغ (سینه)", "خوراک مرغ (ران)"],
    "Wednesday": ["ماهی",  "جوجه (سینه)", "جوجه (ران)"],
}

main_blueprint = Blueprint('main', __name__)
serializer = URLSafeTimedSerializer('pbbivvx9a*o$ng$*kk@$=)h9bq($jc1i9hb44r_1@bbnlhzoc')

def publish_to_rabbitmq(meeting_id, attendees_data):
    # RabbitMQ connection parameters
    credentials = pika.PlainCredentials('guest', 'guest')  # Default RabbitMQ credentials
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost', credentials=credentials)
    )
    channel = connection.channel()

    # Declare the queue
    channel.queue_declare(queue='meeting_emails', durable=True)

    # Message payload
    message = {
        'meeting_id': meeting_id,
        'attendees': attendees_data  # List of (id, first_name, email) tuples
    }

    # Publish message to the queue
    channel.basic_publish(
        exchange='',
        routing_key='meeting_emails',
        body=json.dumps(message).encode(),
        properties=pika.BasicProperties(delivery_mode=2)  # Persistent message
    )

    # Close connection
    connection.close()

@main_blueprint.route('/')
def home():
    return render_template('home.html')

@main_blueprint.route('/login', methods=['GET', 'POST'])
#@limiter.limit("5 per hour")
def login():
    form = LoginForm()
    error=None
    if form.validate_on_submit():
        user = Users.query.filter(Users.email.ilike(form.email.data)).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('main.profile'))
        else:
            error = 'Invalid password'
    return render_template('login.html',form=form, error=error)

@main_blueprint.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('main.home'))

@main_blueprint.route('/register/<token>', methods=['GET', 'POST'])
def register(token):
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600).lower()
    except:
        flash('The registration link is invalid or has expired.', 'danger')
        return redirect(url_for('main.home'))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = Users(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=email,
            phone_number=form.phone_number.data,
            date_of_birth=form.date_of_birth.data,
            group='employee',
            is_superuser=False
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@main_blueprint.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@main_blueprint.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm()
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.phone_number.data = current_user.phone_number
        form.date_of_birth.data = current_user.date_of_birth

    if form.validate_on_submit():
        current_user.first_name = form.first_name.data
        current_user.last_name = form.last_name.data
        current_user.phone_number = form.phone_number.data
        current_user.date_of_birth = form.date_of_birth.data
        
        # Handle profile photo upload
        file = request.files.get('profile_photo')
        if file and file.filename:
            filename = secure_filename(f"{current_user.id}_{file.filename}")
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            current_user.profile_photo = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('main.profile'))
    
    return render_template('edit_profile.html', form=form)

def send_registration_email(email):
    token = serializer.dumps(email, salt='email-confirm')
    msg = Message('Register for Company App', sender='keshavarzi96@gmail.com', recipients=[email])
    msg.body = f'Click the link to register: {url_for("main.register", token=token, _external=True)}'
    mail.send(msg)

@main_blueprint.route('/send_register_link', methods=['GET', 'POST'])
@login_required
def send_register_link():
    if not current_user.is_superuser:
        flash("You don't have permission to send registration links.", "danger")
        return redirect(url_for('main.home'))

    form = SendInviteForm()  # Initialize the form
    if form.validate_on_submit():  # If the form is submitted and valid
        email = form.email.data  # Get the email from the form
        send_registration_email(email)  # Call the function to send the email
        flash("Registration link sent successfully!", "success")
        return redirect(url_for('main.home'))

    return render_template('send_invite.html', form=form)




@main_blueprint.route('/dashboard')
@login_required
def dashboard():
    
    now = now1
    week_start = (now - timedelta(days=(now.weekday() + 2) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)
    two_days_ago = now - timedelta(days=2)

    # Handle "load earlier" parameter
    load_earlier = request.args.get('load_earlier', 'false') == 'true'

    # Base task query
    # if current_user.is_teamlead:
    #     tasks_query = Tasks.query.filter(
    #         or_(
    #             Tasks.assigned_to == current_user.id,
    #             Tasks.created_by == current_user.id,
    #             Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
    #         )
    #     )
    # elif current_user.group in ['Admin', 'CEO', 'Managers']:
    #     tasks_query = Tasks.query
    # else:
    tasks_query = Tasks.query.filter(
            (Tasks.assigned_to == current_user.id) | (Tasks.created_by == current_user.id)
        )

    # Apply time filter: this week by default, all if load_earlier is true
    if not load_earlier:
        tasks_query = tasks_query.filter(Tasks.last_updated >= week_start, Tasks.last_updated < week_end)
    
    tasks = tasks_query.filter(or_(Tasks.status != 'done', Tasks.last_updated >= two_days_ago)).all()

    # Announcements and other data remain unchanged
    announcements = Announcements.query.filter(
        or_(Announcements.target_group == current_user.group, Announcements.target_group.is_(None)),
        Announcements.created_at >= week_start
    ).order_by(Announcements.created_at.desc()).all()
    new_announcements_count = Announcements.query.filter(
        or_(Announcements.target_group == current_user.group, Announcements.target_group.is_(None)),
        Announcements.created_at >= now - timedelta(days=1)
    ).count()
    meetings = Meetings.query.filter(
        Meetings.scheduled_date >= now,
        Meetings.people.contains(str(current_user.id))
    ).order_by(Meetings.scheduled_date.asc()).all()
    sticky_notes = StickyNotes.query.filter_by(user_id=current_user.id).all()

    return render_template('dashboard.html',
                           tasks=tasks,
                           meetings=meetings,
                           sticky_notes=sticky_notes,
                           announcements=announcements,
                           new_announcements_count=new_announcements_count,
                           load_earlier=load_earlier
                           )

@main_blueprint.route('/task/update_status', methods=['POST'])
@login_required
def update_task_status():
    data = request.get_json()
    task_id = data.get('task_id')
    new_status = data.get('status')

    task = Tasks.query.get_or_404(task_id)
    now_iran = now1  # Still needed for manual updates

    # Permission checks remain unchanged
    assignee = Users.query.get(task.assigned_to) if task.assigned_to else None
    is_teamlead_for_group = (current_user.is_teamlead and assignee and assignee.group == current_user.group)

    if not (task.assigned_to == current_user.id or task.created_by == current_user.id or is_teamlead_for_group or current_user.group in ['Admin', 'CEO', 'Managers']):
        return jsonify({'error': 'Unauthorized status update'}), 403

    if new_status == 'finished' and (task.assigned_to == current_user.id or is_teamlead_for_group):
        task.status = 'finished'
        task.last_updated = now_iran
        message = 'Task marked as finished. Awaiting creator approval.'
    elif new_status == 'done' and (task.created_by == current_user.id or is_teamlead_for_group) and task.status == 'finished':
        task.status = 'done'
        task.last_updated = now_iran
        message = 'Task approved and marked as done!'
    elif new_status in ['pending', 'in_progress'] and (task.assigned_to == current_user.id or is_teamlead_for_group):
        task.status = new_status
        task.last_updated = now_iran
        message = 'Task status updated successfully!'
    else:
        return jsonify({'error': 'Invalid status transition'}), 403

    log = TaskLog(
        task_id=task.id,
        user_id=current_user.id,
        action="Status Updated",
        description=f"Task status changed to '{new_status}'"
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({'message': message}), 200


# @main_blueprint.route('/tasks')
# @login_required
# def tasks():
#     filter_type = request.args.get('filter', 'all')  # Default to 'all'
#     now = now1

#     if current_user.group in ['Admin', 'CEO', 'Managers']:
#         if filter_type == 'created_by_me':
#             tasks = Tasks.query.filter(Tasks.created_by == current_user.id).all()
#         elif filter_type == 'assigned_to_me':
#             tasks = Tasks.query.filter(Tasks.assigned_to == current_user.id).all()
#         elif filter_type == 'group':
#             tasks = Tasks.query.filter(
#                 Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
#             ).all()
#         else:  # 'all'
#             tasks = Tasks.query.all()
#     elif current_user.is_teamlead:
#         if filter_type == 'created_by_me':
#             tasks = Tasks.query.filter(Tasks.created_by == current_user.id).all()
#         elif filter_type == 'assigned_to_me':
#             tasks = Tasks.query.filter(Tasks.assigned_to == current_user.id).all()
#         elif filter_type == 'group':
#             tasks = Tasks.query.filter(
#                 Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
#             ).all()
#         else:  # 'all'
#             tasks = Tasks.query.filter(
#                 or_(
#                     Tasks.assigned_to == current_user.id,
#                     Tasks.created_by == current_user.id,
#                     Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
#                 )
#             ).all()
#     else:
#         tasks = Tasks.query.filter(
#             (Tasks.assigned_to == current_user.id) | (Tasks.created_by == current_user.id)
#         ).all()

#     return render_template('view_tasks.html', tasks=tasks, filter_type=filter_type)

@main_blueprint.route('/tasks')
@login_required
def tasks():
    filter_type = request.args.get('filter', 'all')  # Default to 'all'
    time_filter = request.args.get('time_filter', 'all')  # Default to 'all'
    status_filter = request.args.get('status_filter', 'all')  # Default to 'all'
    now = now1  # Current date/time

    # Base query based on user role
    if current_user.group in ['Admin', 'CEO', 'Managers']:
        if filter_type == 'created_by_me':
            base_query = Tasks.query.filter(Tasks.created_by == current_user.id)
        elif filter_type == 'assigned_to_me':
            base_query = Tasks.query.filter(Tasks.assigned_to == current_user.id)
        elif filter_type == 'group':
            base_query = Tasks.query.filter(
                Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
            )
        else:  # 'all'
            base_query = Tasks.query
    elif current_user.is_teamlead:
        if filter_type == 'created_by_me':
            base_query = Tasks.query.filter(Tasks.created_by == current_user.id)
        elif filter_type == 'assigned_to_me':
            base_query = Tasks.query.filter(Tasks.assigned_to == current_user.id)
        elif filter_type == 'group':
            base_query = Tasks.query.filter(
                Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
            )
        else:  # 'all'
            base_query = Tasks.query.filter(
                or_(
                    Tasks.assigned_to == current_user.id,
                    Tasks.created_by == current_user.id,
                    Tasks.assigned_to.in_(db.session.query(Users.id).filter(Users.group == current_user.group))
                )
            )
    else:
        base_query = Tasks.query.filter(
            (Tasks.assigned_to == current_user.id) | (Tasks.created_by == current_user.id)
        )

    # Apply time filter
    if time_filter == 'last_week':
        last_week_start = now1 - timedelta(days=7)
        base_query = base_query.filter(Tasks.created_at >= last_week_start)
    elif time_filter == 'last_month':
        last_month_start = now1 - timedelta(days=30)
        base_query = base_query.filter(Tasks.created_at >= last_month_start)
    elif time_filter == 'this_year':
        year_start = datetime(now.year, 1, 1)
        base_query = base_query.filter(Tasks.created_at >= year_start)
    # 'all' requires no additional filter

    # Apply status filter
    if status_filter != 'all':
        base_query = base_query.filter(Tasks.status == status_filter)

    # Execute the query
    tasks = base_query.all()

    return render_template(
        'view_tasks.html',
        tasks=tasks,
        filter_type=filter_type,
        time_filter=time_filter,
        status_filter=status_filter
    )



@main_blueprint.route('/task/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        assigned_to = request.form.get('assigned_to')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        status = request.form.get('status')
        now_iran = now1

        if not title or not due_date or not priority or not status:
            flash("Title, Due Date, Priority, and Status are required!", "danger")
            return redirect(url_for('main.add_task'))

        if assigned_to and current_user.is_teamlead:
            assignee = Users.query.get(int(assigned_to))
            if assignee.group != current_user.group:
                flash("You can only assign tasks to your group members!", "danger")
                return redirect(url_for('main.add_task'))

        new_task = Tasks(
            title=title,
            description=description,
            assigned_to=int(assigned_to) if assigned_to else None,
            created_by=current_user.id,
            due_date=datetime.strptime(due_date, '%Y-%m-%d'),
            priority=priority,
            status=status,
            last_updated=now_iran
        )
        db.session.add(new_task)
        db.session.flush()

        log = TaskLog(
            task_id=new_task.id,
            user_id=current_user.id,
            action="Created",
            description=f"Task '{title}' created"
        )
        db.session.add(log)
        db.session.commit()

        flash('Task added successfully!', 'success')
        return redirect(url_for('main.tasks'))

    if current_user.is_teamlead:
        users = Users.query.filter(Users.group == current_user.group).all()
    else:
        users = Users.query.all()
    return render_template('add_task.html', users=users)

@main_blueprint.route('/task/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    task = Tasks.query.get_or_404(task_id)
    assignee = Users.query.get(task.assigned_to) if task.assigned_to else None
    is_teamlead_for_group = (current_user.is_teamlead and assignee and assignee.group == current_user.group)

    # Permission check
    if not (task.created_by == current_user.id or task.assigned_to == current_user.id or is_teamlead_for_group or current_user.group in ['Admin', 'CEO', 'Managers']):
        flash("You don't have permission to edit this task.", "danger")
        return redirect(url_for('main.tasks'))

    if request.method == 'POST':
        iran_tz = pytz.timezone('Asia/Tehran')
        now_iran = now1

        title = request.form.get('title')
        assigned_to = request.form.get('assigned_to')
        description = request.form.get('description')
        due_date = request.form.get('due_date')
        priority = request.form.get('priority')
        status = request.form.get('status')
        state_description = request.form.get('state_description') if task.assigned_to == current_user.id else task.state_description  # Only assignee can edit state

        # Team lead restriction on assignment
        if assigned_to and current_user.is_teamlead:
            new_assignee = Users.query.get(int(assigned_to))
            if new_assignee.group != current_user.group:
                flash("You can only assign tasks to your group members!", "danger")
                return redirect(url_for('main.edit_task', task_id=task_id))

        # Status transitions
        if status == 'finished' and (task.assigned_to == current_user.id or is_teamlead_for_group):
            task.status = 'finished'
            flash('Task marked as finished. Awaiting creator approval.', 'info')
        elif status == 'done' and (task.created_by == current_user.id or is_teamlead_for_group) and task.status == 'finished':
            task.status = 'done'
            flash('Task approved and marked as done!', 'success')
        elif status in ['pending', 'in_progress'] and (task.assigned_to == current_user.id or is_teamlead_for_group):
            task.status = status
            flash('Task status updated successfully!', 'success')
        else:
            flash('You cannot update this task to the requested status!', 'danger')
            return redirect(url_for('main.edit_task', task_id=task_id))

        task.title = title
        task.description = description
        task.assigned_to = int(assigned_to) if assigned_to else None
        task.due_date = datetime.strptime(due_date, '%Y-%m-%d')
        task.priority = priority
        task.state_description = state_description
        task.last_updated = now_iran

        db.session.flush()

        # Log task update
        log = TaskLog(
            task_id=task.id,
            user_id=current_user.id,
            action="Updated",
            description=f"Task updated: Status='{status}', State Description='{state_description}'"
        )
        db.session.add(log)
        db.session.commit()

        flash('Task updated successfully!', 'success')
        return redirect(url_for('main.tasks'))

    if current_user.is_teamlead:
        users = Users.query.filter(Users.group == current_user.group).all()
    else:
        users = Users.query.all()
    return render_template('edit_task.html', task=task, users=users)

    
@main_blueprint.route('/task/delete/<int:task_id>', methods=['GET', 'POST'])
@login_required
def delete_task(task_id):
    task = Tasks.query.get_or_404(task_id)
    assignee = Users.query.get(task.assigned_to) if task.assigned_to else None
    is_teamlead_for_group = (current_user.is_teamlead and assignee and assignee.group == current_user.group)

    if not (task.created_by == current_user.id or is_teamlead_for_group or current_user.group in ['Admin', 'CEO', 'Managers']):
        flash("You don't have permission to delete this task.", "danger")
        return redirect(url_for('main.tasks'))

    # Log task deletion
    log = TaskLog(
        task_id=task.id,
        user_id=current_user.id,
        action="Deleted",
        description=f"Task '{task.title}' deleted"
    )
    db.session.add(log)

    # Manually delete all logs associated with the task
    TaskLog.query.filter_by(task_id=task.id).delete()

    # Delete the task
    db.session.delete(task)
    db.session.commit()

    flash('Task deleted successfully!', 'success')
    return redirect(url_for('main.tasks'))



@main_blueprint.route('/meetings')

@login_required

def meetings():
    users = {user.id: f"{user.first_name} {user.last_name}" for user in Users.query.all()}
    if current_user.group in ['Admin', 'CEO', 'Managers']:  # Check if the user has Admin/Managerss/CEO rights
        meetings = Meetings.query.all()  # Admin, CEO, and Managersss see all meetings
        
    else:
        meetings = Meetings.query.filter(Meetings.scheduled_by == current_user.id or Meetings.people.contains(str(current_user.id))).all() # Regular users see only their scheduled meetings
    
    return render_template('view_meetings.html', users=users, meetings=meetings)


@main_blueprint.route('/meeting/<int:meeting_id>')
@login_required
def view_meeting(meeting_id):
    meeting = Meetings.query.get_or_404(meeting_id)

    return render_template('view_meetings.html', meeting=meeting)

@main_blueprint.route('/meeting/edit/<int:meeting_id>', methods=['GET', 'POST'])
@login_required
def edit_meeting(meeting_id):
    meeting = Meetings.query.get_or_404(meeting_id)

    # Only allow Admins, CEO, and Managersss to edit meetings
    if current_user.group not in ['Admin', 'CEO', 'Managerss'] and meeting.scheduled_by != current_user.id:
        flash("You don't have permission to edit this meeting.", "danger")
        return redirect(url_for('main.meetings'))

    if request.method == 'POST':
        meeting.title = request.form.get('title')
        meeting.description = request.form.get('description')
        meeting.scheduled_date = datetime.strptime(request.form.get('scheduled_date'), '%Y-%m-%dT%H:%M')
        meeting.location = request.form.get('location')
        meeting.people = ",".join(request.form.getlist('attendees'))  # Update attendees as comma-separated string
        
        db.session.commit()
        flash('Meeting updated successfully!', 'success')
        return redirect(url_for('main.view_meeting', meeting_id=meeting.id))

    users = Users.query.all()  # Get all users for attendees dropdown
    return render_template('edit_meeting.html', meeting=meeting, users=users)

@main_blueprint.route('/meeting/delete/<int:meeting_id>', methods=['POST'])
@login_required
def delete_meeting(meeting_id):
    meeting = Meetings.query.get_or_404(meeting_id)
    if meeting.scheduled_by != current_user.id:
        flash("You don't have permission to delete this meeting.", "danger")
        return redirect(url_for('main.meetings'))
    
    db.session.delete(meeting)
    db.session.commit()
    flash('Meeting deleted successfully!', 'success')
    return redirect(url_for('main.meetings'))


@main_blueprint.route('/meetings/add', methods=['GET', 'POST'])
@login_required
def add_meeting():
    if request.method == 'POST':
        title = request.form.get('title')
        scheduled_date = request.form.get('scheduled_date')  # e.g., '2025-03-11T10:15'
        location = request.form.get('location')
        attendee_ids = request.form.getlist('attendees')  # List of IDs from multi-select

        if not title or not scheduled_date or not attendee_ids:
            flash('Title, scheduled date, and at least one attendee are required!', 'danger')
            return redirect(url_for('main.add_meeting'))

        iran_tz = pytz.timezone('Asia/Tehran')
        try:
            scheduled_date_iran = iran_tz.localize(datetime.strptime(scheduled_date, '%Y-%m-%dT%H:%M'))
        except ValueError as e:
            flash(f'Invalid date format: {e}', 'danger')
            return redirect(url_for('main.add_meeting'))

        # Convert attendee IDs to a comma-separated string
        attendees_str = ','.join(attendee_ids)

        # Create meeting object
        meeting = Meetings(
            title=title,
            scheduled_date=scheduled_date_iran,
            location=location,
            scheduled_by=current_user.id,
            people=attendees_str
        )
        db.session.add(meeting)
        db.session.commit()

        # Fetch attendees in one query
        attendees = Users.query.filter(Users.id.in_(attendee_ids)).all()

        # Publish to RabbitMQ instead of sending emails directly
        attendees_data = [(attendee.id, attendee.first_name, attendee.email) for attendee in attendees]
        publish_to_rabbitmq(meeting.id, attendees_data)

        # Schedule reminder (e.g., 1 hour before)
        reminder_time = scheduled_date_iran - timedelta(hours=1)
        scheduler.add_job(
            id=f'meeting_reminder_{meeting.id}',
            func=send_meeting_reminder,
            args=[meeting.id],
            trigger='date',
            run_date=reminder_time
        )

        flash('Meeting created! Emails are being sent in the background.', 'success')
        return redirect(url_for('main.dashboard'))

    users = Users.query.all()
    return render_template('add_meeting.html', users=users)

def send_meeting_reminder(meeting_id):
    with scheduler.app.app_context():
        meeting = Meetings.query.get(meeting_id)
        if meeting:
            attendee_ids = meeting.people.split(',')
            attendees = Users.query.filter(Users.id.in_(attendee_ids)).all()
            creator = Users.query.get(meeting.scheduled_by)

            # Use a single SMTP connection for reminders
            with mail.connect() as conn:
                for attendee in attendees:
                    msg = Message(
                        subject=f"⏳ Reminder: {meeting.title} in 1 Hour",
                        sender='keshavarzi96@gmail.com',
                        recipients=[attendee.email]
                    )
                    msg.body = f"""
                    Dear {attendee.first_name},

                    This is a friendly reminder that your meeting **"{meeting.title}"** is scheduled to start in **1 hour**.

                    **Meeting Details:**
                    - **Date & Time:** {meeting.scheduled_date.strftime('%Y-%m-%d %H:%M IRST')}
                    - **Location:** {meeting.location or 'TBD'}

                    Please be prepared and join on time.

                    Best regards,  
                    **Paniz Energy Company**
                    """
                    conn.send(msg)

@main_blueprint.route('/requests/send', methods=['GET', 'POST'])
@login_required
def send_request():
    if request.method == 'POST':
        title = request.form.get('title')
        text = request.form.get('text')
        receiver_id = request.form.get('receiver_id')
        department = request.form.get('department')
        file = request.files.get('attachment')

        if not title or not text or (not receiver_id and not department):
            flash('Title, text, and either a receiver or department are required!', 'danger')
            return redirect(url_for('main.send_request'))

        new_request = Requests(
            title=title,
            text=text,
            sender_id=current_user.id,
            receiver_id=int(receiver_id) if receiver_id else None,
            department=department if department else None
        )

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            new_request.attachment = filename

        db.session.add(new_request)
        db.session.commit()
        flash('Request sent successfully!', 'success')
        return redirect(url_for('main.view_requests'))

    users = Users.query.all()
    departments =['CEO','Managerss','Engineering and Marketing' , 'Finance', 'Office','Admin']
    return render_template('send_request.html', users=users, departments=departments)

# @main_blueprint.route('/requests')
# @login_required
# def view_requests():
#     now = now1
#     today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

#     # Today's sent requests
#     sent_requests = Requests.query.filter(
#         Requests.sender_id == current_user.id,
#         Requests.created_at >= today_start
#     ).order_by(Requests.created_at.desc()).all()

#     # Unread received requests or with unread replies
#     if current_user.is_superuser:
#         received_requests = Requests.query.filter(
#             or_(
#                 Requests.is_read == False,
#                 Requests.replies.any(RequestReplies.created_at > Requests.last_updated)
#             )
#         ).order_by(Requests.created_at.desc()).all()
#     else:
#         received_requests = Requests.query.filter(
#             or_(
#                 and_(Requests.receiver_id == current_user.id, Requests.is_read == False),
#                 and_(Requests.department == current_user.group, Requests.is_read == False),
#                 and_(
#                     or_(
#                         Requests.receiver_id == current_user.id,
#                         Requests.department == current_user.group
#                     ),
#                     Requests.replies.any(and_(
#                         RequestReplies.created_at > Requests.last_updated,
#                         RequestReplies.sender_id != current_user.id
#                     ))
#                 )
#             )
#         ).order_by(Requests.created_at.desc()).all()

#     return render_template('view_requests.html', sent_requests=sent_requests, received_requests=received_requests)


@main_blueprint.route('/requests')
@login_required
def view_requests():
    now = now1  # Current time in Iran timezone
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)  # Start of today

    # Today's sent requests
    sent_requests = Requests.query.filter(
        Requests.sender_id == current_user.id,
        Requests.created_at >= today_start
    ).order_by(Requests.created_at.desc()).all()

    # Received requests: Only show today's requests (unread or with unread replies)
    if current_user.is_superuser:
        received_requests = Requests.query.filter(
            Requests.created_at >= today_start,  # Only today's requests
            or_(
                Requests.is_read == False,
                Requests.replies.any(RequestReplies.created_at > Requests.last_updated)
            )
        ).order_by(Requests.created_at.desc()).all()
    else:
        received_requests = Requests.query.filter(
            Requests.created_at >= today_start,  # Only today's requests
            or_(
                and_(Requests.receiver_id == current_user.id, Requests.is_read == False),
                and_(Requests.department == current_user.group, Requests.is_read == False),
                and_(
                    or_(
                        Requests.receiver_id == current_user.id,
                        Requests.department == current_user.group
                    ),
                    Requests.replies.any(and_(
                        RequestReplies.created_at > Requests.last_updated,
                        RequestReplies.sender_id != current_user.id
                    ))
                )
            )
        ).order_by(Requests.created_at.desc()).all()

    return render_template('view_requests.html', sent_requests=sent_requests, received_requests=received_requests)

@main_blueprint.route('/requests/archive')
@login_required
def requests_archive():
    now = now1
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Archived received requests (read and created before today)
    if current_user.is_superuser:
        archived_received = Requests.query.filter(
            Requests.is_read == True,
            Requests.created_at < today_start
        ).order_by(Requests.created_at.desc()).all()
    else:
        archived_received = Requests.query.filter(
            or_(
                Requests.receiver_id == current_user.id,
                Requests.department == current_user.group
            ),
            Requests.is_read == True,
            Requests.created_at < today_start
        ).order_by(Requests.created_at.desc()).all()

    # Group archived requests by month
    archive_by_month = {}
    for req in archived_received:
        month_key = req.created_at.strftime('%Y-%m')
        if month_key not in archive_by_month:
            archive_by_month[month_key] = []
        archive_by_month[month_key].append(req)

    return render_template('requests_archive.html', archive_by_month=archive_by_month)

@main_blueprint.route('/sent_requests/archive')
@login_required
def sent_requests_archive():
    now = now1
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Archived sent requests (before today)
    archived_sent = Requests.query.filter(
        Requests.sender_id == current_user.id,
        Requests.created_at < today_start
    ).order_by(Requests.created_at.desc()).all()

    archive_by_month = {}
    for req in archived_sent:
        month_key = req.created_at.strftime('%Y-%m')
        if month_key not in archive_by_month:
            archive_by_month[month_key] = []
        archive_by_month[month_key].append(req)

    return render_template('sent_requests_archive.html', archive_by_month=archive_by_month)



@main_blueprint.route('/requests/<int:request_id>', methods=['GET', 'POST'])
@login_required
def view_request(request_id):
    req = Requests.query.get_or_404(request_id)
    
    if not current_user.is_superuser:
        if req.sender_id != current_user.id and req.receiver_id != current_user.id and req.department != current_user.group:
            flash("You don't have permission to view this request.", "danger")
            return redirect(url_for('main.view_requests'))

    if request.method == 'POST':
        reply_text = request.form.get('reply_text')
        status = request.form.get('status')
        file = request.files.get('attachment')

        if reply_text:
            reply = RequestReplies(
                request_id=request_id,
                sender_id=current_user.id,
                text=reply_text
            )
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                reply.attachment = filename
            db.session.add(reply)

        if status and (current_user.id == req.receiver_id or current_user.group == req.department or current_user.is_superuser):
            req.status = status
        req.is_read = True
        db.session.commit()
        flash('Reply sent successfully!' if reply_text else 'Status updated!', 'success')
        return redirect(url_for('main.view_request', request_id=request_id))

    replies = RequestReplies.query.filter_by(request_id=request_id).order_by(RequestReplies.created_at.asc()).all()
    if not req.is_read and (req.receiver_id == current_user.id or req.department == current_user.group):
        req.is_read = True
        db.session.commit()
    return render_template('view_request.html', request=req, replies=replies)

@main_blueprint.route('/download/<filename>')
@login_required
def download_file(filename):
    # Serve the file with its original name and extension
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)




@main_blueprint.route('/sticky_note/add', methods=['POST'])
@login_required
def add_sticky_note():
    content = request.form.get('content')
    if not content:
        flash('Sticky note content cannot be empty!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    sticky_note = StickyNotes(user_id=current_user.id, content=content)
    db.session.add(sticky_note)
    db.session.commit()
    flash('Sticky note added successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@main_blueprint.route('/sticky_note/edit/<int:note_id>', methods=['POST'])
@login_required
def edit_sticky_note(note_id):
    note = StickyNotes.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('You can only edit your own sticky notes!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    content = request.form.get('content')
    if not content:
        flash('Sticky note content cannot be empty!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    note.content = content
    db.session.commit()
    flash('Sticky note updated successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@main_blueprint.route('/sticky_note/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_sticky_note(note_id):
    logger.debug(f"Attempting to delete sticky note {note_id} for user {current_user.id}")
    note = StickyNotes.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to delete note {note_id} owned by {note.user_id}")
        flash('You can only delete your own sticky notes!', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        logger.debug(f"Deleting note {note_id} with content: {note.content}")
        db.session.delete(note)
        db.session.commit()
        logger.info(f"Successfully deleted sticky note {note_id}")
        flash('Sticky note deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to delete sticky note {note_id}: {str(e)}")
        flash(f'Error deleting sticky note: {str(e)}', 'danger')
    
    # Force no-cache redirect
    response = make_response(redirect(url_for('main.dashboard')))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@main_blueprint.route('/announcement/add', methods=['GET', 'POST'])
@login_required
def add_announcement():
    if request.method == 'POST':
        topic = request.form.get('topic')
        text = request.form.get('text')
        target_group = request.form.get('target_group')
        file = request.files.get('attachment')

        if not topic or not text:
            flash('Topic and text are required!', 'danger')
            return redirect(url_for('main.add_announcement'))

        iran_tz = pytz.timezone('Asia/Tehran')
        now_iran =now1

        announcement = Announcements(
            user_id=current_user.id,
            topic=topic,
            text=text,
            target_group=target_group if target_group else None,
            created_at=now_iran  # Explicitly set to current Iran time
        )

        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            announcement.attachment = filename

        db.session.add(announcement)
        db.session.commit()

        # Log the created announcement
        logger.debug(f"Added announcement: {announcement.topic}, Created_at: {announcement.created_at}")

        flash('Announcement added successfully!', 'success')
        return redirect(url_for('main.dashboard'))

    groups = ['CEO','Managerss','Engineering and Marketing' , 'Finance', 'Office','Admin']
    return render_template('add_announcement.html', groups=groups)


@main_blueprint.route('/announcements/viewed', methods=['POST'])
@login_required
def announcements_viewed():
    iran_tz = pytz.timezone('Asia/Tehran')
    now_iran = now1
    # No explicit "is_read" flag; reset count by assuming viewed announcements are older than 24h
    # Alternatively, we could add an is_read flag to Announcements if you prefer persistent tracking
    return jsonify({"status": "success"})

@main_blueprint.route('/announcement_archive')
@login_required
def announcement_archive():
    now = now1  # Server time
    days_since_saturday = (now.weekday() + 2) % 7
    week_start = (now - timedelta(days=days_since_saturday)).replace(hour=0, minute=0, second=0, microsecond=0)  # Midnight on Saturday

    # Log for debugging
    logger.debug(f"Archive - Now: {now}, Week start: {week_start}")

    # Get archived announcements (before this week)
    archived_announcements = Announcements.query.filter(
        or_(
            Announcements.target_group == current_user.group,
            Announcements.target_group.is_(None)
        ),
        Announcements.created_at < week_start
    ).order_by(Announcements.created_at.desc()).all()

    # Log archived announcements
    for ann in archived_announcements:
        logger.debug(f"Archive - Topic: {ann.topic}, Created_at: {ann.created_at}")

    # Group by month
    archive_by_month = {}
    for announcement in archived_announcements:
        month_key = announcement.created_at.strftime('%Y-%m')  # e.g., "2025-02"
        if month_key not in archive_by_month:
            archive_by_month[month_key] = []
        archive_by_month[month_key].append(announcement)

    return render_template('announcement_archive.html', archive_by_month=archive_by_month)



def is_lunch_time():
    now = now1 # Already in Iran time due to global config
    day = now.strftime('%A')  # Day of the week (e.g., "Saturday")
    hour = now.hour
    minute = now.minute
    # Open Saturday to Wednesday, 8:00 AM to 11:30 AM Iran time
    return day in LUNCH_MENU and (8 <= hour < 11 or (hour == 11 and minute <= 30))

@main_blueprint.route('/lunch', methods=['GET', 'POST'])
@login_required
def lunch():
    now = now1  # Current time in Iran
    today = now.strftime('%A')  # e.g., "Monday"

    # Check if today is a valid lunch day
    if today not in LUNCH_MENU:
        flash('Lunch ordering is only available from Saturday to Wednesday.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Restrict regular users to 8:00 AM–11:30 AM; allow office/Admin anytime
    if not is_lunch_time() and current_user.group not in ['Office', 'Admin']:
        flash('Lunch ordering is only available from 8:00 AM to 11:30 AM.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Fetch current user's order for today
    current_order = LunchOrder.query.filter_by(user_id=current_user.id, day=today).first()

    # Handle form submission
    if request.method == 'POST' and (is_lunch_time() or current_user.group in ['Office', 'Admin']):  # Allow Office/Admin anytime
        selected_food = request.form.get('food')
        if selected_food not in LUNCH_MENU[today]:
            flash('Invalid food selection.', 'danger')
            return redirect(url_for('main.lunch'))

        if current_order:
            current_order.food = selected_food
            current_order.ordered_at = now  # Updated to Iran time
            flash(f'Your lunch order updated to: {selected_food}', 'success')
        else:
            new_order = LunchOrder(
                user_id=current_user.id,
                day=today,
                food=selected_food,
                ordered_at=now  # Explicitly set to Iran time
            )
            db.session.add(new_order)
            flash(f'Your lunch order confirmed: {selected_food}', 'success')
        
        db.session.commit()
        return redirect(url_for('main.lunch'))

    # For Office or Admin group: fetch all orders for today
    office_orders = None
    food_summary = None
    if current_user.group in ['Office', 'Admin']:
        office_orders = LunchOrder.query.filter_by(day=today).all()
        food_summary = {}
        for order in office_orders:
            food_summary[order.food] = food_summary.get(order.food, 0) + 1

    return render_template('lunch.html', 
                           menu=LUNCH_MENU[today], 
                           today=today, 
                           current_order=current_order, 
                           office_orders=office_orders, 
                           food_summary=food_summary)

@main_blueprint.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    iran_tz = pytz.timezone('Asia/Tehran')
    now_iran = datetime.now(iran_tz)

    # If last_notifications_viewed is None, default to 30 days ago
    last_viewed = current_user.last_notifications_viewed or (now_iran - timedelta(days=30))

    # Convert last_notifications_viewed from UTC to Iran time (if it's stored in UTC)
    if current_user.last_notifications_viewed:
        last_viewed = current_user.last_notifications_viewed.astimezone(iran_tz)

    # Debugging: Check the last_viewed in Iran time and the current time in Iran time


    # New tasks (last 24 hours, after last viewed)
    new_tasks = Tasks.query.filter(
        Tasks.assigned_to == current_user.id,
        Tasks.last_updated >= last_viewed,  # Use `last_viewed` in Iran time
        Tasks.last_updated >= now_iran - timedelta(days=1)  # Last 24 hours
    ).all()

    task_notifications = [
        {"type": "task", "message": f" Task Update: {task.title}", "time": task.last_updated.strftime('%Y-%m-%d %H:%M IRST')}
        for task in new_tasks
    ]
    last_viewed_iran = last_viewed.astimezone(iran_tz)

    new_meetings = Meetings.query.filter(
        Meetings.created_at >= now_iran,  # upcoming meetings only
        Meetings.people.contains(str(current_user.id)),
        Meetings.created_at <= now_iran + timedelta(days=7),
        Meetings.created_at >= last_viewed_iran  # meetings after last viewed
    ).all()
    # Upcoming meetings (next 7 days, scheduled after last viewed)


    meeting_notifications = [
        {"type": "meeting", "message": f"Upcoming meeting: {meeting.title}", "time": meeting.scheduled_date.strftime('%Y-%m-%d %H:%M IRST')}
        for meeting in new_meetings
    ]

    # New requests (unread, created after last viewed)
    if current_user.is_superuser:
        new_requests = Requests.query.filter(
            Requests.is_read == False,
            Requests.created_at >= last_viewed
        ).all()
    else:
        new_requests = Requests.query.filter(
            or_(
                Requests.receiver_id == current_user.id,
                Requests.department == current_user.group
            ),
            Requests.is_read == False,
            Requests.created_at >= last_viewed
        ).all()

    request_notifications = [
        {"type": "request", "message": f"New request from {req.sender.first_name}: {req.title}", "time": req.created_at.strftime('%Y-%m-%d %H:%M IRST')}
        for req in new_requests
    ]

    # New announcements (last 24 hours, after last viewed)
    new_announcements = Announcements.query.filter(
        or_(
            Announcements.target_group == current_user.group,
            Announcements.target_group.is_(None)
        ),
        Announcements.created_at >= last_viewed,
        Announcements.created_at >= now_iran - timedelta(days=1)
    ).all()

    announcement_notifications = [
        {"type": "announcement", "message": f"New announcement: {ann.topic}", "time": ann.created_at.strftime('%Y-%m-%d %H:%M IRST')}
        for ann in new_announcements
    ]

    notifications = task_notifications + meeting_notifications + request_notifications + announcement_notifications
    notifications.sort(key=lambda x: x['time'], reverse=True)

    return jsonify({
        "count": len(notifications),
        "notifications": notifications
    })

@main_blueprint.route('/notifications/mark_viewed', methods=['GET','POST'])
@login_required
def mark_notifications_viewed():
    
    now_iran = now1

    # Mark all unread requests as read
    if current_user.is_superuser:
        new_requests = Requests.query.filter(Requests.is_read == False).all()
    else:
        new_requests = Requests.query.filter(
            or_(
                Requests.receiver_id == current_user.id,
                Requests.department == current_user.group
            ),
            Requests.is_read == False
        ).all()

    for req in new_requests:
        req.is_read = True

    # Update user's last viewed timestamp
    current_user.last_notifications_viewed = now_iran
    db.session.commit()

    return jsonify({"status": "success"})

@main_blueprint.route('/users', methods=['GET'])
@login_required
def list_users():
    # Only Admins and CEOs can access this page
    if not current_user.is_superuser and current_user.group != 'CEO':
        flash('You do not have permission to view this page.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Fetch all users from the database
    users = Users.query.all()
    return render_template('users.html', users=users)

@main_blueprint.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Only Admins and CEOs can edit users
    if not current_user.is_superuser and current_user.group != 'CEO':
        flash('You do not have permission to edit users.', 'danger')
        return redirect(url_for('main.dashboard'))

    # Fetch the user to be edited
    user = Users.query.get_or_404(user_id)

    if request.method == 'POST':
        # Update user details
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.phone_number = request.form.get('phone_number')
        user.date_of_birth = request.form.get('date_of_birth')
        user.group = request.form.get('group')

        # Update is_teamlead (always visible)
        user.is_teamlead = True if request.form.get('is_teamlead') == 'on' else False

        # Update is_superuser (only for Admin group)
        if user.group == 'Admin':
            user.is_superuser = True if request.form.get('is_superuser') == 'on' else False
        else:
            user.is_superuser = False  # Reset if the user is not in the Admin group

        # Save changes to the database
        db.session.commit()
        flash('User updated successfully!', 'success')
        return redirect(url_for('main.list_users'))

    return render_template('edit_user.html', user=user)

