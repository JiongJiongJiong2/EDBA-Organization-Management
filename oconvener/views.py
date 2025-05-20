# oconvener/views.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
import requests
import sqlite3
import uuid
import sys  
import os  
import pandas as pd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))  
from models import db, Member, Service, BankAccount, SystemLog
from db_utils import validate_email_pattern

import json

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database connection
def get_db_connection():
    conn = sqlite3.connect('instance/EDBA.db')
    conn.row_factory = sqlite3.Row
    return conn

# Payment service utilities
def check_payment_service(organization_id):
    payment_service = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .filter(Service.service_type == 'M')
        .filter(Service.status == 2)
    ).scalar_one_or_none()
    return payment_service is not None

def process_payment(from_org_id, to_org_id, amount):
    try:
        # Get payment service (type 'M')
        payment_service = db.session.execute(
            db.select(Service)
            .filter(Service.organization_id == from_org_id)
            .filter(Service.service_type == 'M')
            .filter(Service.status == 2)  # Must be configured
        ).scalar_one_or_none()
        
        print(f"[Payment Debug] Service check - Found service: {payment_service is not None}")
        if payment_service:
            print(f"[Payment Debug] Service details - URL: {payment_service.url}, Path: {payment_service.path}")
        
        if not payment_service:
            return False, "No transfer service available"
        
        # Get sender's bank account
        from_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == from_org_id)
        ).scalar_one_or_none()
        
        # Get EDBA's bank account (organization_id=0)
        to_account = db.session.execute(
            db.select(BankAccount)
            .filter(BankAccount.organization_id == to_org_id)
        ).scalar_one_or_none()
        
        print(f"[Payment Debug] Bank accounts - From account found: {from_account is not None}, To account found: {to_account is not None}")
        
        if not from_account or not to_account:
            return False, "Bank account information not found"
        
        print(f"[Payment Debug] Bank details - From: {from_account.bank}/{from_account.name}, To: {to_account.bank}/{to_account.name}")
        
        # Prepare payment data
        payment_data = {
            "from_bank": from_account.bank,
            "from_name": from_account.name,
            "from_account": from_account.number,
            "password": from_account.password,
            "to_bank": to_account.bank,
            "to_name": to_account.name,
            "to_account": to_account.number,
            "amount": amount
        }
        
        # Send payment request
        url = payment_service.url + payment_service.path
        print(f"[Payment Debug] Sending request to URL: {url}")
        print(f"[Payment Debug] Request data: {payment_data}")
        response = requests.post(url, json=payment_data)
        print(f"[Payment Debug] Response status code: {response.status_code}")
        print(f"[Payment Debug] Response content: {response.text}")
        
        # Handle response
        if response.status_code == 200:
            result = response.json()
            print(f"[Payment Debug] Parsed JSON response: {result}")
            if result.get('status') == 'success':
                return True, result
        return False, f"Payment failure! Status code: {response.status_code}"
            
    except Exception as e:
        return False, str(e)

oconvener_bp = Blueprint('oconvener', __name__)

# Constants
API_BASE_URL = "http://172.16.160.88:8001"
API_ENDPOINTS = {
    'bank_auth': f"{API_BASE_URL}/hw/bank/authenticate"
}

# Bank Account Management Routes
@oconvener_bp.route('/account/a')
def account_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can access this page', 'error')
        return redirect(url_for('user.dashboard'))
    
    # Get bank account for organization
    bank_account = db.session.execute(
        db.select(BankAccount).filter_by(organization_id=user.organization_id)
    ).scalar_one_or_none()
    
    return render_template('oc_bank_auth.html', user=user, bank_account=bank_account)

@oconvener_bp.route('/bank/authenticate', methods=['POST'])
def bank_authenticate():
    if 'user_id' not in session:
        return jsonify({"status": "fail", "reason": "Please login first"}), 401

    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        return jsonify({"status": "fail", "reason": "Only O-Conveners can manage bank accounts"}), 403

    try:
        data = request.json
        if not data or not all(data.get(field) for field in ["bank", "account_name", "account_number", "password"]):
            return jsonify({"status": "fail", "reason": "All fields are required"}), 400

        # Get or create bank account record
        bank_account = db.session.execute(
            db.select(BankAccount).filter_by(organization_id=user.organization_id)
        ).scalar_one_or_none()

        if bank_account:
            # Update existing record
            bank_account.bank = data['bank']
            bank_account.name = data['account_name']
            bank_account.number = data['account_number']
            bank_account.password = data['password']
        else:
            # Create new record
            bank_account = BankAccount(
                organization_id=user.organization_id,
                bank=data['bank'],
                name=data['account_name'],
                number=data['account_number'],
                password=data['password']
            )
            db.session.add(bank_account)

        db.session.commit()
        return jsonify({"status": "success", "message": "Bank account settings updated successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "fail", "reason": str(e)}), 500

# Member Management Routes
@oconvener_bp.route('/list/a')
def list_a():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))

    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can access this page', 'error')
        return redirect(url_for('user.dashboard'))

    members = db.session.execute(
        db.select(Member)
        .filter_by(organization_id=user.organization_id)
        .order_by(Member.user_type)
    ).scalars().all()

    return render_template('oc_member_list.html', members=members)

@oconvener_bp.route('/update-member-fund/<int:member_id>', methods=['POST'])
def update_member_fund(member_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can manage member funds', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('oconvener.list_a'))
    
    if member.user_id == oc.user_id:
        flash('O-Conveners cannot delete themselves', 'error')
        return redirect(url_for('oconvener.list_a'))

    try:
        new_fund = int(request.form.get('fund', 0))
        if new_fund < 0:
            flash('Fund value cannot be negative', 'error')
        else:
            member.fund = new_fund
            db.session.commit()
            flash('Member fund updated successfully', 'success')
    except ValueError:
        flash('Invalid fund value', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating member fund: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.list_a'))

@oconvener_bp.route('/add-member', methods=['POST'])
def add_member():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can add members', 'error')
        return redirect(url_for('user.dashboard'))
    
    try:
        email = request.form.get('email')
        user_type = request.form.get('user_type')
        
        if user_type not in ['PP', 'PC', 'CC']:
            flash('Invalid user type', 'error')
            return redirect(url_for('oconvener.list_a'))
        
        existing_member = db.session.execute(
            db.select(Member).filter_by(email=email)
        ).scalar_one_or_none()
        
        if existing_member:
            flash('A member with this email already exists', 'error')
            return redirect(url_for('oconvener.list_a'))
        
        # 检查是否有匹配的邮箱模式
        should_auto_activate = False
        if user_type == 'PC' and '@' in email:
            domain = email[email.index('@'):]
            pattern = f'*{domain}'
            existing_pattern = db.session.execute(
                "SELECT 1 FROM email_patterns WHERE organization_id = ? AND pattern = ?",
                [oc.organization_id, pattern]
            ).first()
            should_auto_activate = bool(existing_pattern)
        
        # 根据用户类型和规则决定是否自动激活
        # PP 账户直接激活，PC需要检查pattern匹配是否自动激活，CC需要付费激活
        active_status = 1 if (user_type == 'PP' or should_auto_activate) else 0
        
        new_member = Member(
            email=email,
            user_type=user_type,
            organization_id=oc.organization_id,
            fund=0,
            active_status=active_status
        )
        db.session.add(new_member)
        db.session.commit()
        flash('New member added successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error adding member: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.list_a'))

@oconvener_bp.route('/get-member-fee-details', methods=['GET'])
def get_member_fee_details():
    """获取会员费用详情"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'}), 401
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    try:
        # 获取该组织所有未激活账号
        inactive_members = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=oc.organization_id, active_status=0)
            .filter(Member.user_type.in_(['PP', 'PC', 'CC']))
        ).scalars().all()

        if not inactive_members:
            return jsonify({
                'status': 'error',
                'message': 'No inactive members found'
            }), 400

        # 统计信息
        pp_count = 0
        pc_count = 0
        cc_count = 0
        total_cost = 0
        is_first_pc = True

        # 检查是否已经有激活的PC
        existing_active_pc = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=oc.organization_id, user_type='PC', active_status=1)
        ).first()
        
        if existing_active_pc:
            is_first_pc = False

        # 计算费用和统计各类型成员
        for member in inactive_members:
            if member.user_type == 'CC':
                cc_count += 1
                total_cost += 100
            elif member.user_type == 'PC':
                pc_count += 1
            elif member.user_type == 'PP':
                pp_count += 1

        # 如果是首次添加PC且有PC用户需要激活
        first_pc_fee = 0
        if is_first_pc and pc_count > 0:
            first_pc_fee = 1000
            total_cost += first_pc_fee

        # 确定是否需要付费
        needs_payment = total_cost > 0
        activation_message = (
            f"Activating {pp_count} Data Provider(s), {pc_count} Public Data Consumer(s), "
            f"and {cc_count} Private Data Consumer(s)."
        )

        return jsonify({
            'status': 'success',
            'details': {
                'pp_count': pp_count,
                'pc_count': pc_count,
                'cc_count': cc_count,
                'is_first_pc': is_first_pc,
                'first_pc_fee': first_pc_fee,
                'total_cost': total_cost,
                'needs_payment': needs_payment,
                'activation_message': activation_message
            }
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@oconvener_bp.route('/pay-member-fee', methods=['POST'])
def pay_member_fee():
    """处理会员费支付"""
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'}), 401
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403

    try:
        # Check if bank account is configured
        bank_account = db.session.execute(
            db.select(BankAccount)
            .filter_by(organization_id=oc.organization_id)
        ).scalar_one_or_none()

        if not bank_account:
            return jsonify({
                'status': 'error',
                'message': '请先设置银行账户信息'
            }), 400

        # 获取该组织所有未激活账号
        inactive_members = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=oc.organization_id, active_status=0)
            .filter(Member.user_type.in_(['PP', 'PC', 'CC']))
        ).scalars().all()

        if not inactive_members:
            return jsonify({'status': 'error', 'message': 'No inactive members found'}), 400

        # 计算费用
        total_cost = 0
        pc_count = 0
        is_first_pc = True

        # 检查是否已经有激活的PC
        existing_active_pc = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=oc.organization_id, user_type='PC', active_status=1)
        ).first()
        
        if existing_active_pc:
            is_first_pc = False

        for member in inactive_members:
            if member.user_type == 'CC':
                total_cost += 100
            elif member.user_type == 'PC':
                pc_count += 1

        # 如果是首次添加PC且有PC用户需要激活
        if is_first_pc and pc_count > 0:
            total_cost += 1000

        # 如果没有需要支付的费用
        if total_cost == 0:
            # 直接激活所有成员
            for member in inactive_members:
                member.active_status = 1
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': f'Successfully activated {len(inactive_members)} members without fee'
            })

        # 进行支付
        success, result = process_payment(
            from_org_id=oc.organization_id,
            to_org_id=0,  # system organization
            amount=total_cost
        )

        if not isinstance(result, str) and result.get('status') == 'success':
            # 激活用户
            for member in inactive_members:
                member.active_status = 1
            
            # 如果存在*@格式的PC邮箱，添加到patterns表
            for member in inactive_members:
                if member.user_type == 'PC' and '*@' in member.email:
                    pattern = member.email[member.email.index('*@'):]
                    # 检查是否已存在相同的pattern
                    existing_pattern = db.session.execute(
                        "SELECT 1 FROM email_patterns WHERE organization_id = ? AND pattern = ?",
                        [oc.organization_id, pattern]
                    ).first()
                    
                    if not existing_pattern:
                        db.session.execute(
                            'INSERT INTO email_patterns (organization_id, pattern) VALUES (?, ?)',
                            [oc.organization_id, pattern]
                        )
            
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': f'Successfully activated {len(inactive_members)} members'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Payment failure!'
            }), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@oconvener_bp.route('/edit-member/<int:member_id>', methods=['POST'])
def edit_member(member_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can edit members', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('oconvener.list_a'))
    
    try:
        email = request.form.get('email')
        user_type = request.form.get('user_type')
        
        if user_type not in ['PP', 'PC', 'CC']:
            flash('Invalid user type', 'error')
            return redirect(url_for('oconvener.list_a'))
        
        existing_member = db.session.execute(
            db.select(Member).filter_by(email=email)
        ).scalar_one_or_none()
        if existing_member and existing_member.user_id != member_id:
            flash('A member with this email already exists', 'error')
            return redirect(url_for('oconvener.list_a'))
        
        # 只有当成员当前是激活状态时才考虑改变激活状态
        if member.active_status == 1:
            should_deactivate = False
            deactivate_reason = None

            # 检查是否是第一个PC
            is_first_pc = not db.session.execute(
                db.select(Member)
                .filter_by(organization_id=oc.organization_id, user_type='PC', active_status=1)
                .filter(Member.user_id != member.user_id)  # 排除当前成员
            ).first()

            if user_type == 'PC' and is_first_pc:
                should_deactivate = True
                deactivate_reason = "This will be your first PC member and requires payment for activation"
            elif user_type == 'CC':
                should_deactivate = True
                deactivate_reason = "Private Data Consumer requires payment for activation"

            member.email = email
            member.user_type = user_type
            if should_deactivate:
                member.active_status = 0
                db.session.commit()
                flash(f'Member role updated. {deactivate_reason}', 'warning')
            else:
                db.session.commit()
                flash('Member details updated successfully', 'success')
        else:
            # 未激活的成员保持未激活状态
            member.email = email
            member.user_type = user_type
            db.session.commit()
            flash('Member details updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating member: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.list_a'))

@oconvener_bp.route('/delete-member/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can delete members', 'error')
        return redirect(url_for('user.dashboard'))
    
    member = db.session.get(Member, member_id)
    if not member or member.organization_id != oc.organization_id:
        flash('Member not found in your organization', 'error')
        return redirect(url_for('oconvener.list_a'))
    
    if member.user_id == oc.user_id:
        flash('O-Conveners cannot delete themselves', 'error')
        return redirect(url_for('oconvener.list_a'))

    try:
        db.session.delete(member)
        db.session.commit()
        flash('Member deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting member: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.list_a'))

@oconvener_bp.route('/batch-import-members', methods=['POST'])
def batch_import_members():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    oc = db.session.get(Member, session['user_id'])
    if not oc or oc.user_type != 'OC':
        flash('Only O-Conveners can import members', 'error')
        return redirect(url_for('user.dashboard'))
    
    if 'members_file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('oconvener.list_a'))
    
    file = request.files['members_file']
    if file.filename == '' or not allowed_file(file.filename):
        flash('Invalid file format. Please upload an Excel (.xlsx) file', 'error')
        return redirect(url_for('oconvener.list_a'))
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        df = pd.read_excel(filepath)
        
        required_columns = ['email', 'user_type', 'fund']
        if not all(col in df.columns for col in required_columns):
            flash('Excel file must contain email, user_type, and fund columns', 'error')
            os.remove(filepath)
            return redirect(url_for('oconvener.list_a'))
        
        success_count = 0
        error_count = 0
        
        for _, row in df.iterrows():
            try:
                if not row['email'] or not isinstance(row['email'], str):
                    error_count += 1
                    continue

                if not validate_email_pattern(row['email']):
                    error_count += 1
                    continue
                    
                if not isinstance(row['fund'], (int, float)) or row['fund'] < 0:
                    error_count += 1
                    continue
                    
                if row['user_type'] not in ['PP', 'PC', 'CC']:
                    error_count += 1
                    continue
                
                # 检查是否有匹配的邮箱模式，以及是否需要自动激活
                should_auto_activate = False
                if row['user_type'] == 'PC' and '@' in row['email']:
                    domain = row['email'][row['email'].index('@'):]
                    pattern = f'*{domain}'
                    existing_pattern = db.session.execute(
                        "SELECT 1 FROM email_patterns WHERE organization_id = ? AND pattern = ?",
                        [oc.organization_id, pattern]
                    ).first()
                    should_auto_activate = bool(existing_pattern)

                # 根据规则确定激活状态
                # PP 账户直接激活，PC需要检查pattern匹配是否自动激活，CC需要付费激活
                active_status = 1 if (row['user_type'] == 'PP' or should_auto_activate) else 0

                existing_member = db.session.execute(
                    db.select(Member).filter_by(email=row['email'])
                ).scalar_one_or_none()
                
                if existing_member:
                    existing_member.user_type = row['user_type']
                    existing_member.fund = int(row['fund'])
                    existing_member.active_status = active_status
                else:
                    new_member = Member(
                        email=row['email'],
                        user_type=row['user_type'],
                        organization_id=oc.organization_id,
                        fund=int(row['fund']),
                        active_status=active_status
                    )
                    db.session.add(new_member)
                
                success_count += 1
                
            except Exception:
                error_count += 1
                continue
        
        db.session.commit()
        os.remove(filepath)
        
        flash(f'Successfully processed {success_count} members. {error_count} errors encountered.', 
              'success' if error_count == 0 else 'warning')
        
    except Exception as e:
        db.session.rollback()
        if os.path.exists(filepath):
            os.remove(filepath)
        flash(f'Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.list_a'))

# Service Management Routes
@oconvener_bp.route('/manage-services/<int:organization_id>')
def manage_services(organization_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can manage services', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == organization_id)
        .order_by(Service.service_type)
    ).scalars().all()
    
    return render_template('oc_service_management.html',
                         services=services,
                         user=user)

@oconvener_bp.route('/update-service-status/<int:service_id>', methods=['POST'])
def update_service_status(service_id):
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Please login first'}), 401
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
    
    service = db.session.get(Service, service_id)
    if not service:
        return jsonify({'status': 'error', 'message': 'Service not found'}), 404
    
    try:
        new_status = int(request.form.get('status', 0))
        is_paid = request.form.get('is_paid') is not None
        cost = 0

        if new_status not in [0, 1]:
            flash('Invalid status value', 'error')
            return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))

        if is_paid:
            try:
                cost = int(request.form.get('cost', 0))
                if cost <= 0:
                    flash('Price must be a positive number', 'error')
                    return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))
            except ValueError:
                flash('Invalid price value', 'error')
                return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))
        
        service.status = new_status
        service.cost = cost
        db.session.commit()
        flash('Service status and price updated successfully', 'success')
            
    except ValueError:
        flash('Invalid input values', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service status: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.manage_services', organization_id=service.organization_id))

# Configuration Interface Route
@oconvener_bp.route('/configuration-interface')
def configuration_interface():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can access configuration interface', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    services = db.session.execute(
        db.select(Service)
        .filter(Service.organization_id == user.organization_id)
        .order_by(Service.service_type)
    ).scalars().all()
    
    return render_template('configuration_interface.html', services=services, user=user)

# Service Configuration Routes
@oconvener_bp.route('/submit-configuration/<int:service_id>', methods=['POST'])
def submit_configuration(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can submit configurations', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    service = db.session.get(Service, service_id)
    if not service or service.organization_id != user.organization_id:
        flash('Service not found', 'error')
        return redirect(url_for('oconvener.configuration_interface'))
    
    try:
        # Update service configuration
        service.url = request.form['url']
        service.path = request.form['path']
        service.method = request.form['method']
        service.input_data = request.form['input_json']
        service.output_data = request.form['output_json']
        service.status = 2  # Set status to "Configured"
        
        db.session.commit()
        flash('Service configuration updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating configuration: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.configuration_interface'))

@oconvener_bp.route('/release-service/<int:service_id>', methods=['POST'])
def release_service(service_id):
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'PP':
        flash('Only PP users can release services', 'error')
        return redirect(url_for('user.dashboard', user_type=session.get('user_type')))
    
    service = db.session.get(Service, service_id)
    if not service or service.organization_id != user.organization_id:
        flash('Service not found', 'error')
        return redirect(url_for('oconvener.configuration_interface'))
    
    if service.status != 2:
        flash('Only configured services can be released', 'error')
        return redirect(url_for('oconvener.configuration_interface'))
    
    try:
        service.status = 3  # Set status to "Released"
        db.session.commit()
        flash('Service has been released successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error releasing service: {str(e)}', 'error')
    
    return redirect(url_for('oconvener.configuration_interface'))

# Log Routes
@oconvener_bp.route('/logs')
def view_logs():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can view logs', 'error')
        return redirect(url_for('user.dashboard'))

    page = request.args.get('page', 1, type=int)
    per_page = 20

    # Build the query with filters
    query = (db.select(SystemLog)
             .join(Member, SystemLog.user_id == Member.user_id)
             .filter(Member.organization_id == user.organization_id)
             .filter(Member.user_type.in_(['PP', 'PC', 'CC'])))
    
    # Apply activity type filter
    activity_type = request.args.get('activity_type')
    if activity_type:
        query = query.filter_by(activity_type=activity_type)

    # Apply date filters
    start_date = request.args.get('start_date')
    if start_date:
        query = query.filter(SystemLog.timestamp >= f"{start_date} 00:00:00")
    
    end_date = request.args.get('end_date')
    if end_date:
        query = query.filter(SystemLog.timestamp <= f"{end_date} 23:59:59")

    # Execute query with pagination
    pagination = db.paginate(
        query.order_by(SystemLog.timestamp.desc()),
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template('oc_logs.html', 
                         logs=pagination.items, 
                         pagination=pagination,
                         user=user)

# Main Routes
@oconvener_bp.route('/')
def index():
    return redirect(url_for('oconvener.workspace'))

@oconvener_bp.route('/workspace')
def workspace():
    if 'user_id' not in session:
        flash('Please login first', 'warning')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(Member, session['user_id'])
    if not user or user.user_type != 'OC':
        flash('Only O-Conveners can access this page', 'error')
        return redirect(url_for('user.dashboard'))

    return render_template('oc_main.html', user=user)
