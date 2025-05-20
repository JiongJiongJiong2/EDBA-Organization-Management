from models import db, Member

def find_matching_wildcard_rule(email_suffix):
    """查找匹配的通配符规则"""
    return db.session.execute(
        db.select(Member)
        .filter(Member.email.like(f'*@{email_suffix}'))
    ).scalar_one_or_none()

def get_email_suffix(email):
    """获取邮箱后缀"""
    return email.split('@', 1)[1] if '@' in email else None

def validate_email_pattern(email):
    """验证邮箱格式
    接受普通邮箱或通配符邮箱(*@domain.com)
    """
    if not email or '@' not in email:
        return False
    
    if '*@' in email:
        # 验证通配符格式
        parts = email.split('@')
        return len(parts) == 2 and parts[0] == '*' and parts[1]
    
    # 验证普通邮箱格式
    parts = email.split('@')
    return len(parts) == 2 and parts[0] and parts[1]

def create_member_from_wildcard(email, wildcard_member):
    """根据通配符规则创建新成员"""
    try:
        # 检查是否已有激活的PC用户（包括通配符和非通配符）
        existing_pc = db.session.execute(
            db.select(Member)
            .filter_by(organization_id=wildcard_member.organization_id, user_type='PC', active_status=1)
        ).first()

        # 如果是PC类型用户，根据是否存在已激活的PC决定激活状态
        if wildcard_member.user_type == 'PC':
            active_status = 0 if not existing_pc else 1
        else:
            # 非PC用户保持原有逻辑
            active_status = 1

        new_member = Member(
            email=email,
            user_type=wildcard_member.user_type,
            fund=wildcard_member.fund,
            organization_id=wildcard_member.organization_id,
            active_status=active_status
        )
        db.session.add(new_member)
        db.session.commit()
        return new_member
    except Exception as e:
        db.session.rollback()
        raise e
