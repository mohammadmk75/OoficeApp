from app import db, login_manager,iran_tz
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz



def iran_now():
    return datetime.now(iran_tz)

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone_number = db.Column(db.String(15), nullable=True)
    password = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    group = db.Column(db.String(50), nullable=False, default='employee')
    is_superuser = db.Column(db.Boolean, default=False)
    is_teamlead = db.Column(db.Boolean, default=False)  # New field
    profile_photo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=iran_now)
    last_notifications_viewed = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)
    

class Tasks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    last_updated = db.Column(db.DateTime)
    state_description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=iran_now)  # Added for view_tasks.html
    

    assignee = db.relationship('Users', foreign_keys=[assigned_to], backref='assigned_tasks')
    creator = db.relationship('Users', foreign_keys=[created_by], backref='created_tasks')
    # logs = db.relationship('TaskLog', backref='task', cascade="all, delete-orphan")  # Cascade delete
    
class TaskLog(db.Model):
    __tablename__ = 'task_logs'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=iran_now)

    # Fix relationships to use correct class name 'Tasks' (plural)
    task = db.relationship('Tasks', backref='logs')
    user = db.relationship('Users', backref='task_logs')



class Meetings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    scheduled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Who scheduled the meeting
    scheduled_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    people = db.Column(db.Text, nullable=True)  # Store user IDs as comma-separated values
    created_at = db.Column(db.DateTime, default=iran_now)

    creator = db.relationship('Users', foreign_keys=[scheduled_by], backref='created_meetings')

    # def is_user_participant(self, user_id):
    #     return str(user_id) in self.people.split(',')

    def get_attendees(self):
        return self.people.split(",") if self.people else []
    
class Requests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    department = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=iran_now)
    last_updated = db.Column(db.DateTime, default=iran_now, onupdate=iran_now)
    is_read = db.Column(db.Boolean, default=False)
    attachment = db.Column(db.String(255))
    sender = db.relationship('Users', foreign_keys=[sender_id])
    receiver = db.relationship('Users', foreign_keys=[receiver_id])
    replies = db.relationship('RequestReplies', backref='parent_request', lazy='dynamic')  # Changed backref name

class RequestReplies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('requests.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=iran_now)
    attachment = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False)
    sender = db.relationship('Users')

class StickyNotes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=iran_now)
    updated_at = db.Column(db.DateTime, default=iran_now, onupdate=iran_now)

    user = db.relationship('Users', backref='sticky_notes')

class Announcements(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    target_group = db.Column(db.String(20))  # Null for all, specific group otherwise
    attachment = db.Column(db.String(255))  # File path for attachment
    created_at = db.Column(db.DateTime, default=iran_now)

    user = db.relationship('Users', backref='announcements')


class LunchOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    day = db.Column(db.String(10), nullable=False)  # e.g., "Saturday"
    food = db.Column(db.String(50), nullable=False)  # e.g., "زرشک پلو (سینه)"
    ordered_at = db.Column(db.DateTime, default=iran_now)
        
    user = db.relationship('Users', backref='lunch_orders')

