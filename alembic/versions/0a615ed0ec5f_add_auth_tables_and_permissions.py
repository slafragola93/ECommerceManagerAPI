"""add_auth_tables_and_permissions

Revision ID: 0a615ed0ec5f
Revises: c7d8e9f0a1b2
Create Date: 2026-04-23 13:22:44.981085
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0a615ed0ec5f'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ── 1. MODIFICA TABELLA users ──────────────────────────
    op.add_column('users', sa.Column(
        'totp_secret', sa.String(255), nullable=True
    ))
    op.add_column('users', sa.Column(
        'totp_enabled', sa.Boolean, nullable=False,
        server_default=sa.false()
    ))
    op.add_column('users', sa.Column(
        'mfa_method',
        sa.Enum('totp', 'email', 'none', name='mfa_method_enum'),
        nullable=False, server_default='none'
    ))
    op.add_column('users', sa.Column(
        'deleted_at', sa.DateTime, nullable=True
    ))

    # ── 2. MODIFICA TABELLA roles ──────────────────────────
    op.add_column('roles', sa.Column(
        'description', sa.String(255), nullable=True
    ))
    op.add_column('roles', sa.Column(
        'permission_type',
        sa.Enum('full_crud', 'custom', name='permission_type_enum'),
        nullable=False, server_default='custom'
    ))
    op.add_column('roles', sa.Column(
        'is_system', sa.Boolean, nullable=False,
        server_default=sa.false()
    ))
    op.alter_column('roles', 'name',
        existing_type=sa.String(15),
        type_=sa.String(50),
        nullable=False
    )
    op.drop_column('roles', 'permissions')

    # ── 3. CREA TABELLA app_modules ────────────────────────
    op.create_table(
        'app_modules',
        sa.Column('id_module', sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False,
                  server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False,
                  server_default=sa.true()),
    )

    # ── 4. CREA TABELLA user_module_permissions ────────────
    op.create_table(
        'user_module_permissions',
        sa.Column('id', sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column('id_user', sa.Integer,
                  sa.ForeignKey('users.id_user'), nullable=True),
        sa.Column('id_role', sa.Integer,
                  sa.ForeignKey('roles.id_role'), nullable=True),
        sa.Column('id_module', sa.Integer,
                  sa.ForeignKey('app_modules.id_module'), nullable=False),
        sa.Column('can_read', sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column('can_create', sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column('can_update', sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column('can_delete', sa.Boolean, nullable=False,
                  server_default=sa.false()),
        sa.Column('created_by', sa.Integer,
                  sa.ForeignKey('users.id_user'), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.UniqueConstraint('id_role', 'id_module',
                            name='uq_role_module'),
        sa.UniqueConstraint('id_user', 'id_module',
                            name='uq_user_module'),
    )

    # ── 5. CREA TABELLA refresh_tokens ─────────────────────
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column('id_user', sa.Integer,
                  sa.ForeignKey('users.id_user'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False,
                  unique=True),
        sa.Column('device_info', sa.String(255), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )

    # ── 6. CREA TABELLA mfa_pending_sessions ───────────────
    op.create_table(
        'mfa_pending_sessions',
        sa.Column('id', sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column('id_user', sa.Integer,
                  sa.ForeignKey('users.id_user'), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False,
                  unique=True),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('used_at', sa.DateTime, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('mfa_method',
                  sa.Enum('totp', 'email', name='mfa_pending_method_enum'),
                  nullable=False),
        sa.Column('otp_code_hash', sa.String(255), nullable=True),
    )

    # ── 7. CREA TABELLA auth_logs ──────────────────────────
    op.create_table(
        'auth_logs',
        sa.Column('id', sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column('id_user', sa.Integer,
                  sa.ForeignKey('users.id_user'), nullable=True),
        sa.Column('event', sa.String(100), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('extra_data', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:

    # Elimina in ordine inverso rispetto all'upgrade
    # (prima le tabelle che dipendono da altre)

    op.drop_table('auth_logs')
    op.drop_table('mfa_pending_sessions')
    op.drop_table('refresh_tokens')
    op.drop_table('user_module_permissions')
    op.drop_table('app_modules')

    # Ripristina roles
    op.drop_column('roles', 'is_system')
    op.drop_column('roles', 'permission_type')
    op.drop_column('roles', 'description')
    op.alter_column('roles', 'name',
        existing_type=sa.String(50),
        type_=sa.String(15),
        nullable=True
    )
    op.add_column('roles', sa.Column(
        'permissions', sa.String(10),
        nullable=True, server_default='r'
    ))

    # Ripristina users
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'mfa_method')
    op.drop_column('users', 'totp_enabled')
    op.drop_column('users', 'totp_secret')

    # Elimina gli Enum creati
    sa.Enum(name='mfa_method_enum').drop(op.get_bind())
    sa.Enum(name='permission_type_enum').drop(op.get_bind())
    sa.Enum(name='mfa_pending_method_enum').drop(op.get_bind())