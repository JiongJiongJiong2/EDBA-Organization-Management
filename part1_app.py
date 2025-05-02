# === Start of flask_app.py ===
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
import os
import requests
import sqlite3
app = Flask(__name__)

@app.route('/oc_workspace/account/a')
def account_a():
    return render_template('oc_workspace_bank_auth.html')

# Backend authentication interface processing logic
@app.route('/oc_workspace/bank/authenticate', methods=['POST'])
def bank_authenticate():
    try:
        data = request.json
        required_fields = ["bank", "account_name", "account_number", "password"]

        if not data or not all(field in data for field in required_fields):
            return jsonify({"status": "fail", "reason": "Missing fields"}), 400

        # Send POST request to external API for authentication
        external_api_url = "http://172.16.160.88:8001/hw/bank/authenticate"
        response = requests.post(external_api_url, json=data)

        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@app.route('/oc_workspace/list/a')
def list_a():
    try:
        # Connect to database
        conn = sqlite3.connect('yourdatabase.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM members")
        rows = cursor.fetchall()
        conn.close()

        # Convert to HTML table
        table_html = "<h2>Member list</h2><table border='1'><tr>"
        # Get column names
        col_names = [description[0] for description in cursor.description]
        for col in col_names:
            table_html += f"<th>{col}</th>"
        table_html += "</tr>"

        for row in rows:
            table_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        table_html += "</table>"

        return table_html

    except Exception as e:
        return f"<h2>Error reading member data: {e}</h2>"

@app.route('/oc_workspace/information/a')
def information_a():
    try:
        # Connect to database
        conn = sqlite3.connect('yourdatabase.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM organizations")
        rows = cursor.fetchall()
        conn.close()

        # Convert to HTML table
        table_html = "<h2>Organization Information</h2><table border='1'><tr>"
        # Get column names
        col_names = [description[0] for description in cursor.description]
        for col in col_names:
            table_html += f"<th>{col}</th>"
        table_html += "</tr>"

        for row in rows:
            table_html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        table_html += "</table>"

        return table_html

    except Exception as e:
        return f"<h2>Error reading member data: {e}</h2>"

@app.route('/oc_workspace/service/a')
def service_a():
    org_id = 1  # Example, should be read from session
    conn = sqlite3.connect('yourdatabase.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT enabled FROM service_settings
        WHERE org_id = ? AND service_name = 'course_info'
    """, (org_id,))
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:  # Service is enabled
        return '<h2>Course information sharing service is enabled</h2>'
    else:
        return '<h2>Course information sharing service is currently disabled</h2>'

@app.route('/oc_workspace/service/a/settings', methods=['GET', 'POST'])
def course_service_settings():
    org_id = 1  # Example
    if request.method == 'POST':
        new_status = request.form.get('enabled') == 'on'
        conn = sqlite3.connect('yourdatabase.db')
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO service_settings (org_id, service_name, enabled)
            VALUES (?, 'course_info', ?)
            ON CONFLICT(org_id, service_name) DO UPDATE SET enabled=excluded.enabled
        """, (org_id, int(new_status)))
        conn.commit()
        conn.close()
        return redirect(url_for('course_service_settings'))

    # Show current settings
    conn = sqlite3.connect('yourdatabase.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT enabled FROM service_settings
        WHERE org_id = ? AND service_name = 'course_info'
    """, (org_id,))
    result = cursor.fetchone()
    current_status = bool(result[0]) if result else False
    conn.close()

    checked_attr = 'checked' if current_status else ''
    return f"""
        <h2>Course Information Sharing Settings</h2>
        <form method="POST">
            <label>
                <input type="checkbox" name="enabled" {checked_attr}>
                Enable Course Information Sharing Service
            </label>
            <br><br>
            <button type="submit">Save Settings</button>
        </form>
    """

@app.route('/oc_workspace/service/b')
def service_b():
    return render_template('oc_workspace_student_auth.html')
@app.route('/oc_workspace/student/authenticate', methods=['POST'])
def student_authenticate():
    try:
        name = request.form.get('name')
        student_id = request.form.get('id')
        photo = request.files.get('photo')

        if not all([name, student_id, photo]):
            return jsonify({"status": "fail", "reason": "Missing fields"}), 400

        # 构建请求
        files = {'photo': (secure_filename(photo.filename), photo.stream, photo.mimetype)}
        data = {'name': name, 'id': student_id}
        api_url = 'http://172.16.160.88:8001/hw/student/authenticate'

        response = requests.post(api_url, data=data, files=files)
        if response.status_code != 200:
            return jsonify({"status": "fail", "reason": "External API error"}), 502

        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "fail", "reason": str(e)}), 500

@app.route('/oc_workspace/service/c',methods=['POST','GET'])
def service_c():
    try:
        # Request all thesis data, keywords empty or use wildcard, adjust according to actual interface behavior
        response = requests.post("http://172.16.160.88:8001/hw/thesis/search", json={"keywords": ""})
        thesis_results = response.json() if isinstance(response.json(), list) else [response.json()]
    except Exception as e:
        return f"<h2>Failed to get thesis data: {e}</h2>"

    # Render all theses
    html_output = "<h2>Thesis Sharing</h2><hr>"
    for thesis in thesis_results:
        title = thesis.get('title', 'No Title')
        abstract = thesis.get('abstract', 'No Abstract')
        html_output += f"<h4>{title}</h4><p>{abstract}</p><hr>"

    return html_output

@app.route('/oc_workspace/service/d', methods=['GET', 'POST'])
def service_d():
    org_id = request.args.get('org_id', type=int)  # User's organization ID (should be read from session)
    conn = sqlite3.connect('yourdatabase.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, description, is_paid, price 
        FROM thesis_services 
        WHERE visible = 1 OR org_id = ?
    """, (org_id,))

    services = cursor.fetchall()
    conn.close()

    html_output = "<h2>Thesis Download Service</h2><hr>"
    for service in services:
        service_id, title, description, is_paid, price = service
        html_output += f"<h4>{title}</h4><p>{description}</p>"
        if is_paid:
            html_output += f"<p><strong>Price：</strong>¥{price}</p>"
            html_output += f"<form action='/purchase_service' method='POST'><input type='hidden' name='service_id' value='{service_id}'><button type='submit'>Pay to Download</button></form>"
        else:
            html_output += f"<form action='/download_service' method='GET'><input type='hidden' name='service_id' value='{service_id}'><button type='submit'>Free Download</button></form>"
        html_output += "<hr>"

    return html_output

@app.route('/oc_workspace')
def index():
    return redirect(url_for('workspace'))

@app.route('/oc_workspace/account', methods=['GET', 'POST'])
def workspace():
    return render_template('oc_workspace_oc-workspace.html')

# Create static file directories
def create_directories():
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

if __name__ == '__main__':
    create_directories()
    # Create templates directory
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5001)

# === End of flask_app.py ===

# === Start of flask_app1.py ===
from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
from datetime import datetime
import sqlite3
import uuid

app = Flask(__name__)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('yourdatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

# Sample user data
users = [
]

@app.route('/o_convener/questions/a', methods=['GET', 'POST'])
def question_a():
    if request.method == 'POST':
        try:
            # Get form data
            description = request.form.get('description', '')
            sender_id = request.form.get('sender_id', '')
            
            if not description or not sender_id:
                return jsonify({'success': False, 'message': 'Please fill in all information'})
            
            conn = get_db_connection()
            # Generate unique question ID
            question_id = str(uuid.uuid4())
            
            # Insert new question
            conn.execute("""
                INSERT INTO questions (question_id, description, sender_id, status, answer)
                VALUES (?, ?, ?, 0, '')
            """, (question_id, description, sender_id))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Question submitted successfully'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'Submission failed: {str(e)}'})
    
    return render_template('o-convener_question_a.html')

@app.route('/o_convener/questions/b')
def question_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    current_user_id = request.args.get('user_id', '')  # Get current user ID from request
    
    # Get answered questions (status = 1)
    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1 
        AND q.sender_id = ?
        AND (q.description LIKE ? OR m.email LIKE ? OR q.answer LIKE ?)
        """
        questions = conn.execute(query, (current_user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1 
        AND q.sender_id = ?
        """
        questions = conn.execute(query, (current_user_id,)).fetchall()
    
    conn.close()
    
    return render_template('o-convener_question_b.html', 
                         questions=questions,
                         current_user_id=current_user_id,
                         search_query=search_query)

@app.route('/o_convener')
def index():
    return redirect(url_for('o_convener'))

@app.route('/o_convener/users', methods=['GET', 'POST'])
def o_convener():
    search_query = ""
    filtered_users = users
    
    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        if search_query:
            filtered_users = [user for user in users if search_query.lower() in user['user_number'].lower()]
    
    return render_template('o-convener.html',
                          users=filtered_users, 
                          search_query=search_query)

@app.route('/o_convener/workspace')
def workspace():
    return render_template('o-convener_workspace.html')

# Create necessary directories for static files
def create_directories():
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

if __name__ == '__main__':
    create_directories()
    # Create templates directory
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000)

# === End of flask_app1.py ===

# === Start of flask_app2.py ===
from flask import Flask, render_template, request, redirect, url_for
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Create necessary directories for static files
def create_directories():
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('yourdatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

# Get table structure
def get_table_structure():
    conn = get_db_connection()
    cursor = conn.execute("PRAGMA table_info(members)")
    columns = [column[1] for column in cursor.fetchall()]
    conn.close()
    return columns

# Sample user data
users = [
]

@app.route('/t_admin/users/a')
def users_a():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get table structure
    columns = get_table_structure()
    print("Table structure:", columns)  # Print table structure for debugging
    
    if search_query:
        # Search function
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        """
        users = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        # Default display all users
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members
        """
        users = conn.execute(query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_users_a.html', users=users, search_query=search_query)

@app.route('/t_admin/users/b')
def users_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get all E-Admin users
    if search_query:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'E-Admin' 
        AND (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        """
        users = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'E-Admin'
        """
        users = conn.execute(query).fetchall()
    
    # Get all non-E-Admin users for authorization
    non_eadmin_query = """
    SELECT user_id, email, user_type, organization_id 
    FROM members 
    WHERE user_type != 'E-Admin'
    """
    non_eadmin_users = conn.execute(non_eadmin_query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_users_b.html', users=users, non_eadmin_users=non_eadmin_users, search_query=search_query)

@app.route('/t_admin/users/c')
def users_c():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get all SE-Admin users
    if search_query:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'SE-Admin' 
        AND (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        """
        users = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'SE-Admin'
        """
        users = conn.execute(query).fetchall()
    
    # Get all E-Admin users for authorization
    eadmin_query = """
    SELECT user_id, email, user_type, organization_id 
    FROM members 
    WHERE user_type = 'E-Admin'
    """
    eadmin_users = conn.execute(eadmin_query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_users_c.html', users=users, eadmin_users=eadmin_users, search_query=search_query)

@app.route('/t_admin/users/d')
def users_d():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get all T-Admin users
    if search_query:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'T-Admin' 
        AND (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        """
        users = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT user_id, email, user_type, organization_id 
        FROM members 
        WHERE user_type = 'T-Admin'
        """
        users = conn.execute(query).fetchall()
    
    # Get all non-E-Admin users for authorization
    non_eadmin_query = """
    SELECT user_id, email, user_type, organization_id 
    FROM members 
    WHERE user_type != 'E-Admin'
    """
    non_eadmin_users = conn.execute(non_eadmin_query).fetchall()
    
    # Get all E-Admin users for revoking authorization
    eadmin_query = """
    SELECT user_id, email, user_type, organization_id 
    FROM members 
    WHERE user_type = 'E-Admin'
    """
    eadmin_users = conn.execute(eadmin_query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_users_d.html', users=users, non_eadmin_users=non_eadmin_users, eadmin_users=eadmin_users, search_query=search_query)

@app.route('/t_admin/update_answer/<question_id>', methods=['POST'])
def update_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '').strip()  # Use strip() to remove leading/trailing spaces
    
    # If answer is empty, change status to unanswered(0)
    if not new_answer:
        conn.execute("UPDATE questions SET answer = ?, status = 0 WHERE question_id = ?", (new_answer, question_id))
    else:
        conn.execute("UPDATE questions SET answer = ? WHERE question_id = ?", (new_answer, question_id))
    
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_a'))

@app.route('/t_admin/questions/a')
def question_a():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get answered questions (status = 1)
    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1 
        AND (q.description LIKE ? OR m.email LIKE ? OR q.answer LIKE ?)
        """
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1
        """
        questions = conn.execute(query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_question_a.html', questions=questions, search_query=search_query)

@app.route('/t_admin/submit_answer/<question_id>', methods=['POST'])
def submit_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '')
    conn.execute("UPDATE questions SET answer = ?, status = 1 WHERE question_id = ?", (new_answer, question_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_b'))

@app.route('/t_admin/questions/b')
def question_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')
    
    # Get unanswered questions (status = 0)
    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0 
        AND (q.description LIKE ? OR m.email LIKE ?)
        """
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email as sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0
        """
        questions = conn.execute(query).fetchall()
    
    conn.close()
    
    return render_template('t-admin_question_b.html', questions=questions, search_query=search_query)

@app.route('/t_admin')
def index():
    return redirect(url_for('user_management'))

@app.route('/t_admin/users', methods=['GET', 'POST'])
def user_management():
    search_query = ""
    filtered_users = users
    
    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        if search_query:
            filtered_users = [user for user in users if search_query.lower() in user['user_number'].lower()]
    
    return render_template('t-admin_user_management.html',
                          users=filtered_users, 
                          search_query=search_query)

@app.route('/t_admin/main')
def main_page():
    return render_template('t-admin_main_page.html')

@app.route('/t_admin/grant_eadmin/<user_id>', methods=['POST'])
def grant_eadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'E-Admin' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

@app.route('/t_admin/revoke_eadmin/<user_id>', methods=['POST'])
def revoke_eadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'User' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

@app.route('/t_admin/grant_seadmin/<user_id>', methods=['POST'])
def grant_seadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'SE-Admin' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

@app.route('/t_admin/revoke_seadmin/<user_id>', methods=['POST'])
def revoke_seadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'E-Admin' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

if __name__ == '__main__':
    create_directories()
    # Create templates directory
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000)

# === End of flask_app2.py ===

# === Start of flask_app4.py ===
from flask import Flask, render_template, request, redirect, url_for
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Create necessary directories for static files
def create_directories():
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('yourdatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

# Get table structure (example utility)
def get_table_structure():
    conn = get_db_connection()
    cursor = conn.execute("PRAGMA table_info(members)")
    columns = [column[1] for column in cursor.fetchall()]
    conn.close()
    return columns

# Sample placeholder for potential use
users = []

# Route: E-Admin 管理 (已授权和未授权列表)
@app.route('/e_admin/users/b')
def users_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    # 查询已授权 E-Admin 用户
    if search_query:
        query = '''
        SELECT user_id, email, user_type, organization_id
        FROM members
        WHERE user_type = 'E-Admin'
          AND (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        '''
        users_list = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = '''
        SELECT user_id, email, user_type, organization_id
        FROM members
        WHERE user_type = 'E-Admin'
        '''
        users_list = conn.execute(query).fetchall()

    # 查询未授权用户
    non_eadmin_query = '''
    SELECT user_id, email, user_type, organization_id
    FROM members
    WHERE user_type != 'E-Admin'
    '''
    non_eadmin_users = conn.execute(non_eadmin_query).fetchall()
    conn.close()

    return render_template('e_admin_user_b.html', users=users_list, non_eadmin_users=non_eadmin_users, search_query=search_query)

# 授权为 E-Admin
@app.route('/e_admin/grant_eadmin/<user_id>', methods=['POST'])
def grant_eadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'E-Admin' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('users_b'))

# 取消 E-Admin 授权
@app.route('/e_admin/revoke_eadmin/<user_id>', methods=['POST'])
def revoke_eadmin(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE members SET user_type = 'User' WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('users_b'))

# Route: 已回答问题列表
@app.route('/e_admin/questions/a', methods=['GET'])
def question_a():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if search_query:
        query = '''
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1
          AND (q.question_id LIKE ? OR q.description LIKE ? OR m.email LIKE ?)
        '''
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = '''
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1
        '''
        questions = conn.execute(query).fetchall()

    conn.close()
    return render_template('e_admin_question_a.html', questions=questions, search_query=search_query)

# Route: 未回答问题列表
@app.route('/e_admin/questions/b', methods=['GET'])
def question_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if search_query:
        query = '''
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0
          AND (q.question_id LIKE ? OR q.description LIKE ? OR m.email LIKE ?)
        '''
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = '''
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0
        '''
        questions = conn.execute(query).fetchall()

    conn.close()
    return render_template('e_admin_question_b.html', questions=questions, search_query=search_query)

# 更新已回答问题的答案
@app.route('/e_admin/update_answer/<question_id>', methods=['POST'])
def update_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '')

    if not new_answer:
        conn.execute("UPDATE questions SET answer = ?, status = 0 WHERE question_id = ?", (new_answer, question_id))
    else:
        conn.execute("UPDATE questions SET answer = ? WHERE question_id = ?", (new_answer, question_id))

    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_a'))

# 提交未回答问题的答案
@app.route('/e_admin/submit_answer/<question_id>', methods=['POST'])
def submit_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '')
    conn.execute("UPDATE questions SET answer = ?, status = 1 WHERE question_id = ?", (new_answer, question_id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_b'))

# 主页面路由
@app.route('/e_admin/main')
def mian_page1():
    return render_template('e_admin_main.html')
@app.route('/e_admin')
def main_page2():
    return render_template('e_admin_user_management.html')

if __name__ == '__main__':
    create_directories()
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000)

# === End of flask_app4.py ===

# === Start of flask_app5.py ===
from flask import Flask, render_template, request, redirect, url_for
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Create necessary directories for static files and templates
def create_directories():
    os.makedirs('static/images', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    os.makedirs('templates', exist_ok=True)

# Database connection function
def get_db_connection():
    conn = sqlite3.connect('yourdatabase.db')
    conn.row_factory = sqlite3.Row
    return conn

# Optional helper to get table structure
def get_table_structure():
    conn = get_db_connection()
    cursor = conn.execute("PRAGMA table_info(members)")
    columns = [column[1] for column in cursor.fetchall()]
    conn.close()
    return columns

# In-memory users list for user management (example)
users = [
    # Example: {'user_number': '001', 'name': 'Alice', ...}
]

# User Management (E-Admin)
@app.route('/se_admin/users', methods=['GET', 'POST'])
def user_management():
    search_query = ""
    filtered_users = users

    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        if search_query:
            filtered_users = [user for user in users if search_query.lower() in user['user_number'].lower()]

    return render_template(
        'se_admin_user_management.html',
        users=filtered_users,
        search_query=search_query
    )

# Main Page
@app.route('/se_admin')
def main_page1():
    return render_template('se_admin_user_management.html')

@app.route('/se_admin/main')
def main_page2():
    return render_template('se_admin_main_page.html')

# SE-Admin Management
@app.route('/se_admin/users/c')
def users_c():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if search_query:
        query = """
        SELECT user_id, email, user_type, organization_id
        FROM members
        WHERE user_type = 'SE-Admin'
          AND (user_id LIKE ? OR email LIKE ? OR organization_id LIKE ?)
        """
        se_admins = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT user_id, email, user_type, organization_id
        FROM members
        WHERE user_type = 'SE-Admin'
        """
        se_admins = conn.execute(query).fetchall()

    eadmin_query = """
    SELECT user_id, email, user_type, organization_id
    FROM members
    WHERE user_type = 'E-Admin'
    """
    e_admins = conn.execute(eadmin_query).fetchall()
    conn.close()

    return render_template(
        'se_admin_management.html',
        se_admins=se_admins,
        e_admins=e_admins,
        search_query=search_query
    )

# Answered Questions
@app.route('/se_admin/questions/a')
def question_a():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1
          AND (q.description LIKE ? OR m.email LIKE ? OR q.answer LIKE ?)
        """
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 1
        """
        questions = conn.execute(query).fetchall()

    conn.close()
    return render_template(
        'se_admin_answered_questions.html',
        questions=questions,
        search_query=search_query
    )

# Unanswered Questions
@app.route('/se_admin/questions/b')
def question_b():
    conn = get_db_connection()
    search_query = request.args.get('search', '')

    if search_query:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0
          AND (q.description LIKE ? OR m.email LIKE ?)
        """
        questions = conn.execute(query, (f'%{search_query}%', f'%{search_query}%')).fetchall()
    else:
        query = """
        SELECT q.question_id, q.description, q.sender_id, m.email AS sender, q.answer
        FROM questions q
        JOIN members m ON q.sender_id = m.user_id
        WHERE q.status = 0
        """
        questions = conn.execute(query).fetchall()

    conn.close()
    return render_template(
        'se_admin_unanswered_questions.html',
        questions=questions,
        search_query=search_query
    )

# Update Answer (for answered questions)
@app.route('/se_admin/update_answer/<question_id>', methods=['POST'])
def update_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '').strip()

    if not new_answer:
        conn.execute(
            "UPDATE questions SET answer = ?, status = 0 WHERE question_id = ?",
            (new_answer, question_id)
        )
    else:
        conn.execute(
            "UPDATE questions SET answer = ? WHERE question_id = ?",
            (new_answer, question_id)
        )

    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_a'))

# Submit Answer (for unanswered questions)
@app.route('/se_admin/submit_answer/<question_id>', methods=['POST'])
def submit_answer(question_id):
    conn = get_db_connection()
    new_answer = request.form.get('answer', '')
    conn.execute(
        "UPDATE questions SET answer = ?, status = 1 WHERE question_id = ?",
        (new_answer, question_id)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('question_b'))

# Grant/Revoke E-Admin
@app.route('/se_admin/grant_eadmin/<user_id>', methods=['POST'])
def grant_eadmin(user_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE members SET user_type = 'E-Admin' WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

@app.route('/se_admin/revoke_eadmin/<user_id>', methods=['POST'])
def revoke_eadmin(user_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE members SET user_type = 'User' WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

# Grant/Revoke SE-Admin
@app.route('/se_admin/grant_seadmin/<user_id>', methods=['POST'])
def grant_seadmin(user_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE members SET user_type = 'SE-Admin' WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

@app.route('/se_admin/revoke_seadmin/<user_id>', methods=['POST'])
def revoke_seadmin(user_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE members SET user_type = 'E-Admin' WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('user_management'))

if __name__ == '__main__':
    create_directories()
    app.run(debug=True, port=5000)

# === End of flask_app5.py ===

