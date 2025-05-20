import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, Member

def fix_wildcard_patterns():
    """
    处理已有的通配符邮箱，并添加到 email_patterns 表
    """
    print("开始执行通配符邮箱修复...")
    try:
        # 获取所有PC类型且邮箱以*@开头的成员
        wildcard_members = db.session.execute(
            db.select(Member)
            .filter(Member.user_type == 'PC')
            .filter(Member.email.like('*@%'))
        ).scalars().all()

        if not wildcard_members:
            print("没有找到需要处理的通配符邮箱")
            return

        for member in wildcard_members:
            try:
                # 检查是否已存在相同的pattern
                pattern = member.email
                existing_pattern = db.session.execute(
                    "SELECT 1 FROM email_patterns WHERE organization_id = ? AND pattern = ?",
                    [member.organization_id, pattern]
                ).first()

                if not existing_pattern:
                    # 添加到 email_patterns 表
                    db.session.execute(
                        'INSERT INTO email_patterns (organization_id, pattern) VALUES (?, ?)',
                        [member.organization_id, pattern]
                    )
                    print(f"已添加pattern: {pattern} 到组织 {member.organization_id}")

                # 确保通配符账户本身被激活
                if member.active_status != 1:
                    member.active_status = 1
                    print(f"已激活通配符账户: {member.email}")

            except Exception as e:
                print(f"处理成员 {member.email} 时出错: {str(e)}")
                continue

        db.session.commit()
        print("通配符邮箱修复完成")

    except Exception as e:
        db.session.rollback()
        print(f"执行过程中出错: {str(e)}")

if __name__ == '__main__':
    fix_wildcard_patterns()
