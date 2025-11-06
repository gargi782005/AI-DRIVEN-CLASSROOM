from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory , jsonify, Response
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import flash
import os
import cv2
import numpy as np
import base64
import re
import imutils
import json, os

app = Flask(__name__)

# Directory to store uploaded videos
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(os.path.join(app.root_path, app.config['UPLOAD_FOLDER']), exist_ok=True)

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  
app.config['MYSQL_PASSWORD'] = 'root' 
app.config['MYSQL_DB'] = 'student_portal'
app.config['MYSQL_PORT'] =3305
app.secret_key = os.urandom(24)

mysql = MySQL(app)

# Fixed passwords for Admin and HOD
# In a real-world scenario, these should be securely stored in environment variables.
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS_HASH = generate_password_hash("admin") 
HOD_EMAIL = "hod@example.com"
HOD_PASS_HASH = generate_password_hash("hod")

@app.before_request
def initialize_users():
    """Initializes admin and HOD accounts with fixed passwords."""
    cur = mysql.connection.cursor()
    # Check if admin exists
    cur.execute("SELECT * FROM admins WHERE email = %s", (ADMIN_EMAIL,))
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username, email, password_hash) VALUES (%s, %s, %s)",
                    ('Admin', ADMIN_EMAIL, ADMIN_PASS_HASH))
        mysql.connection.commit()
    # Check if HOD exists
    cur.execute("SELECT * FROM hods WHERE email = %s", (HOD_EMAIL,))
    if not cur.fetchone():
        cur.execute("INSERT INTO hods (username, email, password_hash) VALUES (%s, %s, %s)",
                    ('HOD', HOD_EMAIL, HOD_PASS_HASH))
        mysql.connection.commit()
    cur.close()   

@app.route('/')
def home():
    """Renders the login page."""
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles student registration."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        # Hash the password for security
        password_hash = generate_password_hash(password)
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO students (username, email, password_hash) VALUES (%s, %s, %s)",
                        (username, email, password_hash))
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('home'))
        except Exception as e:
            cur.close()
            return f"An error occurred: {e}"
    return render_template('register.html')

@app.route('/login_student', methods=['POST'])
def login_student():
    """Handles student login."""
    email = request.form['email']
    password = request.form['password']
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM students WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    
    if user and check_password_hash(user[3], password):
        session['logged_in'] = True
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['role'] = 'student'
        return redirect(url_for('dashboard'))
    else:
        return "Invalid credentials. Please try again."

@app.route('/login_admin', methods=['POST'])
def login_admin():
    """Handles admin login."""
    email = request.form['email']
    password = request.form['password']
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM admins WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    
    if user and check_password_hash(user[3], password):
        session['logged_in'] = True
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['role'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    else:
        return "Invalid credentials. Please try again."

@app.route('/login_hod', methods=['POST'])
def login_hod():
    """Handles HOD login."""
    email = request.form['email']
    password = request.form['password']
    
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM hods WHERE email = %s", (email,))
    user = cur.fetchone()
    cur.close()
    
    if user and check_password_hash(user[3], password):
        session['logged_in'] = True
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['role'] = 'hod'
        return redirect(url_for('hod_dashboard'))
    else:
        return "Invalid credentials. Please try again."
    


#    hod_dashboard     #

@app.route('/hod_dashboard')
def hod_dashboard():
    """Renders the HOD dashboard."""
    if 'logged_in' in session and session['role'] == 'hod':
        username = session.get('username')
        cur = mysql.connection.cursor()
        
        # Example: Fetch top 5 videos by movement score
        cur.execute("SELECT v.title, va.score FROM videos v JOIN video_analysis va ON v.id = va.video_id ORDER BY va.score DESC LIMIT 5")
        top_videos = cur.fetchall()
        cur.close()
        
        return render_template('hod_dashboard.html', username=username, top_videos=top_videos)
    
    # This return statement is for when the if condition is false
    return "Access Denied."

@app.route('/upload_video', methods=['POST'])
def upload_video():
    """Handles video upload from admin/HOD."""
    if 'logged_in' in session and (session['role'] == 'hod' or session['role'] == 'admin'):
        if 'video_file' not in request.files:
            return "No video file part"
        file = request.files['video_file']
        if file.filename == '':
            return "No selected file"
        
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            title = request.form['title']
            
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO videos (title, url) VALUES (%s, %s)", (title, filename))
            mysql.connection.commit()
            cur.close()
            
            # Change the redirect to the new view_videos route
            return redirect(url_for('view_videos'))
    return "Access Denied."

@app.route('/add_lecture', methods=['POST'])
def add_lecture():
    if 'logged_in' in session and session['role'] == 'hod':
        data = request.get_json()
        title = data.get('title')
        date = data.get('date')
        time = data.get('time')
        status = data.get('status')

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO lectures (title, date, time, status)
            VALUES (%s, %s, %s, %s)
        """, (title, date, time, status))
        mysql.connection.commit()
        cur.close()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Access Denied'}), 403

@app.route('/analytics')
def analytics():
    """Renders the HOD analytics page."""
    if 'logged_in' in session and session['role'] == 'hod':
        username = session.get('username')
        return render_template('analytics.html', username=username)
    return "Access Denied."

@app.route('/get_student_analytics')
def get_student_analytics():
    """Return attendance and focus % for all students."""
    if 'logged_in' in session and session['role'] == 'hod':
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username FROM students")
        students = cur.fetchall()

        analytics = []
        for s in students:
            student_id = s[0]
            username = s[1]

            # Attendance %
            cur.execute("SELECT COUNT(*) FROM lectures")
            total_lectures = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM attendance WHERE student_id=%s AND status='Attended'", (student_id,))
            attended = cur.fetchone()[0]

            attendance_percent = round((attended / total_lectures) * 100, 2) if total_lectures else 0

            # Focus %
            cur.execute("SELECT AVG(focus_percent) FROM attendance WHERE student_id=%s", (student_id,))
            focus_avg = cur.fetchone()[0]
            focus_percent = round(focus_avg, 2) if focus_avg else 0

            analytics.append({
                'username': username,
                'attendance_percent': attendance_percent,
                'focus_percent': focus_percent
            })

        cur.close()
        return jsonify(analytics)
    return jsonify({'error': 'Access Denied'}), 403

@app.route('/supervise_students')
def supervise_students():
    """Admin/HOD can view and manage students with lectures, status, focus % and emotion."""
    if 'logged_in' in session and (session['role'] == 'hod' or session['role'] == 'admin'):
        username = session.get('username')
        cur = mysql.connection.cursor()

        # Fetch all students
        cur.execute("SELECT id, username FROM students")
        students_data = cur.fetchall()

        # Fetch all lectures
        cur.execute("SELECT id, title FROM lectures")
        lectures_data = cur.fetchall()
        lecture_dict = {row[0]: row[1] for row in lectures_data}

        # Prepare the list of records for the table
        records = []
        for student in students_data:
            student_id = student[0]
            student_name = student[1]

            cur.execute("""
                SELECT lecture_id, status, focus_percent, emotion 
                FROM attendance 
                WHERE student_id = %s
            """, (student_id,))
            attendance_data = cur.fetchall()

            for row in attendance_data:
                lecture_id = row[0]
                status = row[1]
                focus_percent = row[2]
                emotion = row[3] if len(row) > 3 else 'N/A'
                records.append({
                    'username': student_name,
                    'lecture_title': lecture_dict.get(lecture_id, 'N/A'),
                    'status': status,
                    'focus_percent': focus_percent,
                    'emotion': emotion
                })

        cur.close()

        return render_template('supervise_students.html', students=records, username=username)

    return "Access Denied."


@app.route('/view_videos')
def view_videos():
    """Displays all uploaded videos for admin/HOD."""
    if 'logged_in' in session and (session['role'] == 'hod' or session['role'] == 'admin'):
        username = session.get('username')
        cur = mysql.connection.cursor()
        cur.execute("SELECT title, url FROM videos")
        videos_data = cur.fetchall()
        cur.close()

        videos = [{'title': row[0], 'url': url_for('uploaded_file', filename=row[1])} for row in videos_data]
        
        return render_template('view_videos.html', username=username, videos=videos)
    return "Access Denied."

@app.route('/delete_video', methods=['POST'])
def delete_video():
    if 'logged_in' not in session or session.get('role') not in ['admin', 'hod']:
        return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 403

    data = request.get_json()
    title = data.get('title')

    if not title:
        return jsonify({'status': 'error', 'message': 'No video title provided'}), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT url FROM videos WHERE title = %s", (title,))
    video = cur.fetchone()

    if not video:
        cur.close()
        return jsonify({'status': 'error', 'message': 'Video not found'}), 404

    video_url = video[0]
    file_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], video_url)

    cur.execute("DELETE FROM videos WHERE title = %s", (title,))
    mysql.connection.commit()
    cur.close()

    if os.path.exists(file_path):
        os.remove(file_path)

    return jsonify({'status': 'success'})

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    # send_from_directory automatically joins the directory and filename
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

#    student_dashboard   #

@app.route('/dashboard')
def dashboard():
    if 'logged_in' in session and session['role'] == 'student':
        username = session.get('username')
        student_id = session.get('user_id')
        cur = mysql.connection.cursor()

        #  Fetch videos for students
        cur.execute("SELECT title, url FROM videos LIMIT 2")
        videos_data = cur.fetchall()
        videos = [{'title': row[0], 'url': url_for('uploaded_file', filename=row[1])} for row in videos_data]

        #  Fetch lectures from database
        cur.execute("SELECT id, title, date, time FROM lectures ORDER BY date ASC")
        lectures_data = cur.fetchall()
        lectures = [
            {
                'id': row[0],
                'title': row[1],
                'date': row[2].strftime('%Y-%m-%d'),
                'time': row[3]
            }
            for row in lectures_data
        ]

        #  Fetch attendance status for this student
        cur.execute("SELECT lecture_id, status FROM attendance WHERE student_id = %s", (student_id,))
        attendance_data = {row[0]: row[1] for row in cur.fetchall()}

        #  Calculate overall attendance percentage based on total lectures available
        total_lectures = len(lectures)
        attended_lectures = sum(1 for status in attendance_data.values() if status == 'Attended')

        if total_lectures > 0:
            attendance_percent = round((attended_lectures / total_lectures) * 100, 2)
        else:
            attendance_percent = 0

        cur.close()

        return render_template(
            'dashboard.html',
            videos=videos,
            username=username,
            lectures=lectures,
            attendance=attendance_data,
            attendance_percent=attendance_percent
        )

    return "Please log in to access this page."
@app.route('/get_attendance_percent')
def get_attendance_percent():
    if 'logged_in' in session and session['role'] == 'student':
        student_id = session.get('user_id')
        cur = mysql.connection.cursor()

        # Fetch all lectures
        cur.execute("SELECT id FROM lectures")
        total_lectures = len(cur.fetchall())

        # Fetch attended ones
        cur.execute("SELECT COUNT(*) FROM attendance WHERE student_id = %s AND status = 'Attended'", (student_id,))
        attended = cur.fetchone()[0]

        cur.close()

        if total_lectures > 0:
            percent = round((attended / total_lectures) * 100, 2)
        else:
            percent = 0

        return jsonify({'attendance_percent': percent})
    return jsonify({'attendance_percent': 0})

@app.route('/student_videos')
def student_videos():
    """Displays all uploaded videos for students."""
    if 'logged_in' in session and session['role'] == 'student':
        username = session.get('username')
        cur = mysql.connection.cursor()
        cur.execute("SELECT title, url FROM videos")
        videos_data = cur.fetchall()
        cur.close()

        videos = [{'title': row[0], 'url': url_for('uploaded_file', filename=row[1])} for row in videos_data]
        return render_template('student_videos.html', videos=videos, username=username)
    return "Please log in to access this page."

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    return redirect(url_for('home'))


#    admin_dashboard     #

@app.route('/admin_dashboard')
def admin_dashboard():
    # Only allow admin access
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))  # Fixed redirect

    cur = mysql.connection.cursor()

    # --- Count totals ---
    cur.execute("SELECT COUNT(*) FROM students")
    total_students = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM hods")
    total_hods = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM lectures")
    total_lectures = cur.fetchone()[0]

    # --- Average engagement (if attendance table exists) ---
    cur.execute("SELECT AVG(focus_percent) FROM attendance")
    avg_engagement = cur.fetchone()[0] or 0
    avg_engagement = round(avg_engagement, 2)

    # --- Updated: Recent lectures summary with student name ---
    cur.execute("""
        SELECT 
            l.title AS lecture_title,
            COALESCE(h.username, 'HOD') AS uploaded_by,
            s.username AS student_name,
            COALESCE(a.focus_percent, 0) AS engagement_percent,
            l.date
        FROM attendance a
        JOIN lectures l ON a.lecture_id = l.id
        JOIN students s ON a.student_id = s.id
        LEFT JOIN hods h ON l.uploaded_by = h.id
        ORDER BY l.date DESC
        LIMIT 10
    """)
    lectures = cur.fetchall()
    cur.close()

    return render_template(
        'admin_dashboard.html',
        total_students=total_students,
        total_hods=total_hods,
        total_lectures=total_lectures,
        avg_engagement=avg_engagement,
        lectures=lectures,
        admin_name=session.get('username', 'Admin')
    )

@app.route('/manage_users', methods=['GET'])
def manage_users():
    """Admin can view and manage all users: students, HODs, admins."""
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))

    cur = mysql.connection.cursor()

    # Combine all users into a single list for display
    cur.execute("""
        SELECT id, username AS name, email, 'admin' AS role FROM admins
        UNION
        SELECT id, username AS name, email, 'hod' AS role FROM hods
        UNION
        SELECT id, username AS name, email, 'student' AS role FROM students
        ORDER BY role, id
    """)
    users = cur.fetchall()
    cur.close()

    return render_template('manage_users.html', users=users)

@app.route('/update_user/<role>/<int:user_id>', methods=['POST'])
def update_user(role, user_id):
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')

    table = 'students' if role == 'student' else 'hods' if role == 'hod' else 'admins'

    cur = mysql.connection.cursor()
    cur.execute(f"UPDATE {table} SET username=%s, email=%s WHERE id=%s", (name, email, user_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'User updated successfully!'})

@app.route('/delete_user/<role>/<int:user_id>', methods=['POST'])
def delete_user(role, user_id):
    table = 'students' if role == 'student' else 'hods' if role == 'hod' else 'admins'

    cur = mysql.connection.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cur.close()
    return jsonify({'message': 'User deleted successfully!'})

@app.route('/system_reports')
def system_reports():
    """Display system-wide reports: total lectures, attendance, average engagement, and recent logs."""
    if 'logged_in' not in session or session.get('role') != 'admin':
        return redirect(url_for('home'))

    cur = mysql.connection.cursor()

    # Total lectures
    cur.execute("SELECT COUNT(*) FROM lectures")
    total_lectures = cur.fetchone()[0]

    # Total attendance records
    cur.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cur.fetchone()[0]

    # Average engagement
    cur.execute("SELECT AVG(focus_percent) FROM attendance")
    avg_engagement = cur.fetchone()[0] or 0
    avg_engagement = round(avg_engagement, 2)

    # Detailed logs: attendance + lectures + students + uploaded_by HOD
    cur.execute("""
        SELECT 
            s.username AS student_name,
            l.title AS lecture_title,
            COALESCE(h.username, 'HOD') AS uploaded_by,
            a.status,
            a.focus_percent,
            a.attended_at
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN lectures l ON a.lecture_id = l.id
        LEFT JOIN hods h ON l.uploaded_by = h.id
        ORDER BY a.attended_at DESC
        LIMIT 50
    """)
    logs_data = cur.fetchall()

    # Prepare logs for template
    logs = []
    for row in logs_data:
        logs.append({
            "student_name": row[0],
            "lecture_name": row[1],
            "uploaded_by": row[2],
            "status": row[3],
            "engagement": row[4],
            "date": row[5].strftime("%Y-%m-%d %H:%M")
        })

    cur.close()

    return render_template(
        'system_reports.html',
        admin_name=session.get('username', 'Admin'),
        total_lectures=total_lectures,
        total_attendance=total_attendance,
        avg_engagement=avg_engagement,
        logs=logs
    )

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Allow logged-in users (student/HOD/admin) to update their details."""
    if 'logged_in' not in session:
        flash("Please login first.", "danger")
        return redirect(url_for('home'))

    role = session.get('role')
    user_id = session.get('user_id')

    # Determine correct table
    table = 'students' if role == 'student' else 'hods' if role == 'hod' else 'admins'

    cur = mysql.connection.cursor()
    cur.execute(f"SELECT id, username, email FROM {table} WHERE id = %s", (user_id,))
    user = cur.fetchone()

    if request.method == 'POST':
        new_name = request.form['name']
        new_email = request.form['email']
        new_password = request.form['password']

        if new_password.strip():
            hashed_password = generate_password_hash(new_password)
            cur.execute(f"""
                UPDATE {table} SET username=%s, email=%s, password_hash=%s WHERE id=%s
            """, (new_name, new_email, hashed_password, user_id))
        else:
            cur.execute(f"""
                UPDATE {table} SET username=%s, email=%s WHERE id=%s
            """, (new_name, new_email, user_id))

        mysql.connection.commit()
        flash("Settings updated successfully!", "success")

        # Update session values
        session['username'] = new_name

        cur.close()
        return redirect(url_for('settings'))

    cur.close()
    return render_template('settings.html', user=user, role=role)

# FACE + EYE DETECTION WITH FOCUS TRACKING

camera = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier('haarcascades/haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier('haarcascades/haarcascade_eye.xml')

# Track focus data
student_focus_data = {
    'focus_count': 0,
    'total_frames': 0,
    'focus_percent': 0
}

def gen_frames():
    """Detect face & eyes to calculate focus score live."""
    global student_focus_data
    while True:
        success, frame = camera.read()
        if not success:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        student_focus_data['total_frames'] += 1

        for (x, y, w, h) in faces:
            roi_gray = gray[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_gray)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)

            if len(eyes) >= 2:
                student_focus_data['focus_count'] += 1
                label = "Focused"
                color = (0, 255, 0)
            else:
                label = "Distracted"
                color = (0, 0, 255)

            cv2.putText(frame, label, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # Update live focus %
        if student_focus_data['total_frames'] > 0:
            student_focus_data['focus_percent'] = (
                student_focus_data['focus_count'] / student_focus_data['total_frames']) * 100

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/attend/<int:lecture_id>')
def attend(lecture_id):
    if 'logged_in' in session and session['role'] == 'student':
        username = session.get('username')
        return render_template('attend.html', username=username, lecture_id=lecture_id)
    return "Access Denied."


@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/leave_attendance/<int:lecture_id>')
def leave_attendance(lecture_id):
    global student_focus_data
    if 'logged_in' in session and session['role'] == 'student':
        student_id = session.get('user_id')

        # Calculate focus %
        if student_focus_data['total_frames'] > 0:
            focus_percent = round(
                (student_focus_data['focus_count'] / student_focus_data['total_frames']) * 100, 2)
        else:
            focus_percent = 0

        import random
        emotions = ['Happy', 'Neutral', 'Sad', 'Angry', 'Surprised', 'Focused']
        emotion = random.choice(emotions)

        #  Save attendance, focus %, and emotion into the database
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO attendance (student_id, lecture_id, status, focus_percent, emotion)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                status=%s, 
                focus_percent=%s, 
                emotion=%s
        """, (
            student_id, lecture_id, 'Attended', focus_percent, emotion,
            'Attended', focus_percent, emotion
        ))
        mysql.connection.commit()
        cur.close()

        # Reset focus data
        student_focus_data = {'focus_count': 0, 'total_frames': 0, 'focus_percent': 0}
        session['focus_percent'] = focus_percent

        return redirect(url_for('dashboard'))
    return "Access Denied."


@app.route('/get_focus_data')
def get_focus_data():
    """API to send live focus/emotion data to the dashboard."""
    global student_focus_data
    if 'logged_in' in session and session['role'] == 'student':
        return jsonify({
            'focus_percent': round(student_focus_data['focus_percent'], 2),
            'focus_count': student_focus_data['focus_count'],
            'total_frames': student_focus_data['total_frames']
        })
    return jsonify({'error': 'Access Denied'}), 403

@app.route('/submit_feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    video_title = data.get('video_title')
    feedback = data.get('feedback')
    student_name = session.get('username', 'Unknown')

    feedback_entry = {
        "student_name": student_name,
        "video_title": video_title,
        "feedback": feedback
    }

    feedback_list = []
    if os.path.exists('feedback_data.json'):
        with open('feedback_data.json', 'r') as f:
            feedback_list = json.load(f)

    feedback_list.append(feedback_entry)

    with open('feedback_data.json', 'w') as f:
        json.dump(feedback_list, f, indent=4)

    return jsonify({"status": "success"})

@app.route('/get_feedback')
def get_feedback():
    """Return all stored student feedback to display on supervise page"""
    feedback_list = []
    if os.path.exists('feedback_data.json'):
        with open('feedback_data.json', 'r') as f:
            feedback_list = json.load(f)
    return jsonify(feedback_list)

if __name__ == '__main__':
    app.run(debug=True)