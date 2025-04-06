from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime, timedelta
import json
import os
import uuid
import dotenv
from dotenv import load_dotenv
import os
load_dotenv()
password=os.getenv("PASSWORD")

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this to a random string in production

# Data storage - in a real app, you'd use a database
DATA_FILE = "voting_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    else:
        # Initialize with empty data structure
        data = {
            "events": {}
        }
        save_data(data)
        return data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# Function to format datetime for display
def format_datetime(dt_str):
    dt = datetime.fromisoformat(dt_str)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Admin password - in a real app, use proper authentication
ADMIN_PASSWORD = password  # Change this in production

@app.route('/')
def index():
    data = load_data()
    current_time = datetime.now()
    
    # Separate active and finished events
    active_events = {}
    finished_events = {}
    
    for event_id, event in data["events"].items():
        end_time = datetime.fromisoformat(event["end_time"])
        if current_time > end_time:
            finished_events[event_id] = event
        else:
            active_events[event_id] = event
            # Add formatted end time for display
            active_events[event_id]["end_time_formatted"] = format_datetime(event["end_time"])
    
    # Check which events the user has voted on
    voted_events = session.get('voted_events', [])
    
    return render_template('index.html', 
                          active_events=active_events, 
                          finished_events=finished_events,
                          voted_events=voted_events)

@app.route('/event/<event_id>')
def event_detail(event_id):
    data = load_data()
    event = data["events"].get(event_id)
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('index'))
    
    current_time = datetime.now()
    end_time = datetime.fromisoformat(event["end_time"])
    event_active = current_time <= end_time
    
    # Format end time for display
    event["end_time_formatted"] = format_datetime(event["end_time"])
    
    # Check if user has already voted
    voted_events = session.get('voted_events', [])
    has_voted = event_id in voted_events
    
    return render_template('event.html', 
                          event=event, 
                          event_id=event_id, 
                          active=event_active,
                          has_voted=has_voted)

@app.route('/vote/<event_id>', methods=['POST'])
def vote(event_id):
    data = load_data()
    event = data["events"].get(event_id)
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('index'))
    
    current_time = datetime.now()
    end_time = datetime.fromisoformat(event["end_time"])
    
    if current_time > end_time:
        flash("This event has ended.")
        return redirect(url_for('event_detail', event_id=event_id))
    
    option = request.form.get('option')
    if option not in event["options"]:
        flash("Invalid option selected.")
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Check if user has already voted (using session)
    voted_events = session.get('voted_events', [])
    if event_id in voted_events:
        flash("You have already voted on this event.")
        return redirect(url_for('event_detail', event_id=event_id))
    
    # Record vote
    event["votes"][option] = event["votes"].get(option, 0) + 1
    
    # Mark as voted in session
    voted_events.append(event_id)
    session['voted_events'] = voted_events
    
    # Save data
    save_data(data)
    
    flash("Your vote has been recorded!")
    return redirect(url_for('event_detail', event_id=event_id))

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return render_template('admin_login.html')
    
    data = load_data()
    current_time = datetime.now().isoformat()
    return render_template('admin.html', events=data["events"], current_time=current_time)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password')
    
    if password == ADMIN_PASSWORD:
        session['is_admin'] = True
        return redirect(url_for('admin'))
    else:
        flash("Incorrect password.")
        return redirect(url_for('admin'))

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))

@app.route('/admin/create', methods=['GET', 'POST'])
def create_event():
    if not session.get('is_admin'):
        return redirect(url_for('admin'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        
        # Get duration in hours, minutes, and seconds
        duration_hours = int(request.form.get('duration_hours', 0))
        duration_minutes = int(request.form.get('duration_minutes', 0))
        duration_seconds = int(request.form.get('duration_seconds', 0))
        
        options = request.form.getlist('options')
        
        # Remove empty options
        options = [opt for opt in options if opt.strip()]
        
        if not title or not options:
            flash("Title and at least one option are required.")
            return render_template('create_event.html')
        
        if duration_hours == 0 and duration_minutes == 0 and duration_seconds == 0:
            flash("Duration must be greater than zero.")
            return render_template('create_event.html')
        
        # Create new event
        event_id = str(uuid.uuid4())
        
        # Calculate end time based on hours, minutes, and seconds
        duration = timedelta(
            hours=duration_hours,
            minutes=duration_minutes,
            seconds=duration_seconds
        )
        end_time = datetime.now() + duration
        
        data = load_data()
        data["events"][event_id] = {
            "title": title,
            "description": description,
            "options": options,
            "votes": {},
            "created_at": datetime.now().isoformat(),
            "end_time": end_time.isoformat()
        }
        save_data(data)
        
        flash("Event created successfully!")
        return redirect(url_for('admin'))
    
    return render_template('create_event.html')

@app.route('/results/<event_id>')
def results(event_id):
    data = load_data()
    event = data["events"].get(event_id)
    
    if not event:
        flash("Event not found.")
        return redirect(url_for('index'))
    
    # Format end time for display
    event["end_time_formatted"] = format_datetime(event["end_time"])
    
    return render_template('results.html', event=event, event_id=event_id)

if __name__ == '__main__':
    app.run(debug=True)