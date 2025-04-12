from app.models import Users

def user_name_filter(user_id):
    user = Users.query.get(user_id)
    return f"{user.first_name} {user.last_name}" if user else "Unknown"
