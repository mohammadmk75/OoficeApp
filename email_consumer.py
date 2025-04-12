import pika
import json
from flask_mail import Mail, Message
from app import db, create_app, mail
from app.models import Meetings, Users

app = create_app()  # Initialize Flask app for context
mail = Mail(app)    # Re-initialize mail with app context

def callback(ch, method, properties, body):
    with app.app_context():  # Ensure Flask app context
        data = json.loads(body.decode())
        meeting_id = data['meeting_id']
        attendees_data = data['attendees']  # List of (id, first_name, email)

        meeting = Meetings.query.get(meeting_id)
        if not meeting:
            print(f"Meeting {meeting_id} not found!")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        creator = Users.query.get(meeting.scheduled_by)
        if not creator:
            print(f"Creator for meeting {meeting_id} not found!")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        # Send emails using a single SMTP connection
        with mail.connect() as conn:
            for attendee_id, first_name, email in attendees_data:
                msg = Message(
                    subject=f"📅 New Meeting Invitation: {meeting.title}",
                    sender='keshavarzi96@gmail.com',
                    recipients=[email]
                )
                msg.body = f"""
                Dear {first_name},

                You have been invited to a meeting at **Paniz Energy Company**.

                **Meeting Details:**

                - **Title:** {meeting.title}

                - **Date & Time:** {meeting.scheduled_date.strftime('%Y-%m-%d %H:%M IRST')}
                
                - **Location:** {meeting.location or 'TBD'}

                Please make sure to be on time.

                Best regards,  
                **Paniz Energy Company**
                """
                conn.send(msg)
                print(f"Sent email to {email} for meeting {meeting_id}")

        # Acknowledge the message
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    credentials = pika.PlainCredentials('guest', 'guest')
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost', credentials=credentials)
    )
    channel = connection.channel()

    channel.queue_declare(queue='meeting_emails', durable=True)
    channel.basic_qos(prefetch_count=1)  # Process one message at a time
    channel.basic_consume(queue='meeting_emails', on_message_callback=callback)

    print("Starting email consumer. Waiting for messages...")
    channel.start_consuming()

if __name__ == '__main__':
    main()