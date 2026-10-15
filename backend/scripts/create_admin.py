"""受控创建/提升管理员账号（观澜管理中心）。

用法（在 backend 目录下）：

    # 交互式输入密码（推荐）
    .venv\\Scripts\\python.exe -m scripts.create_admin --username admin --nickname 管理员

    # 通过环境变量传入密码（适合无人值守；不要写进命令行历史）
    AUREL_ADMIN_PASSWORD=xxx python -m scripts.create_admin --username admin

规则：
- 密码不落地：交互式用 getpass 读取，绝不写进代码、日志或命令行参数；
- 若用户名已存在，则将该用户提升为 admin（不改密码，除非显式提供 --reset-password）；
- 注册接口不允许自设角色，本脚本是设置管理员的唯一入口。
"""

import argparse
import getpass
import os
import re
import sys

from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from app.schemas.auth import USERNAME_PATTERN
from app.services.password_service import hash_password, verify_password


def _read_password(env_name: str | None, *, confirm: bool) -> str:
    env_value = os.environ.get(env_name) if env_name else None
    if env_value:
        print("已从环境变量读取密码")
        return env_value
    password = getpass.getpass("请输入管理员密码（8-64 位，需包含字母和数字）: ")
    if confirm:
        again = getpass.getpass("请再次输入以确认: ")
        if password != again:
            sys.exit("两次输入的密码不一致，已取消")
    if not 8 <= len(password) <= 64:
        sys.exit("密码长度需在 8-64 位之间")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        sys.exit("密码需同时包含字母和数字")
    return password


def main() -> None:
    parser = argparse.ArgumentParser(description="创建或提升观澜 AUREL 管理员账号")
    parser.add_argument("--username", required=True, help="管理员用户名（3-24 位中英文/数字/下划线）")
    parser.add_argument("--nickname", default="管理员", help="昵称（默认：管理员）")
    parser.add_argument(
        "--password-env",
        default=None,
        help="从该环境变量读取密码（默认交互式输入；推荐交互式）",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="用户已存在时同时重置密码（默认仅提升角色）",
    )
    args = parser.parse_args()

    username = args.username.strip()
    if not USERNAME_PATTERN.fullmatch(username):
        sys.exit("用户名需为 3-24 位中英文、数字或下划线")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
        if user is None:
            password = _read_password(args.password_env, confirm=True)
            user = User(
                username=username,
                nickname=args.nickname.strip() or "管理员",
                password_hash=hash_password(password),
                role="admin",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"已创建管理员账号：{user.username}（id={user.id}）")
        else:
            user.role = "admin"
            if args.reset_password:
                password = _read_password(args.password_env, confirm=True)
                if verify_password(password, user.password_hash):
                    print("新密码与原密码相同，跳过重置")
                else:
                    user.password_hash = hash_password(password)
            db.commit()
            print(f"已将现有用户 {user.username}（id={user.id}）提升为管理员")


if __name__ == "__main__":
    main()
