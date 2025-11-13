"""remove topics and topic_relations

Revision ID: 3c9a9f_remove_topics
Revises: 2a36883ac910
Create Date: 2025-11-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c9a9f_remove_topics'
down_revision = '2a36883ac910'
branch_labels = None
depends_on = None


def upgrade():
    # Drop topic_relations table if exists
    try:
        op.drop_table('topic_relations')
    except Exception:
        pass

    # Drop topic_id column from questions (if exists)
    try:
        op.drop_column('questions', 'topic_id')
    except Exception:
        pass

    # Drop topics table
    try:
        op.drop_table('topics')
    except Exception:
        pass


def downgrade():
    # Recreate topics table
    op.create_table('topics',
        sa.Column('topic_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('topic_id')
    )

    # Recreate topic_relations table
    op.create_table('topic_relations',
        sa.Column('relation_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('parent_name', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['topics.topic_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('relation_id')
    )

    # Add topic_id column back to questions
    op.add_column('questions', sa.Column('topic_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'questions', 'topics', ['topic_id'], ['topic_id'], ondelete='SET NULL')
