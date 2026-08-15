#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/10 14:39
@Author     : 歌白
@File       : upload_file.py
"""

from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    PrimaryKeyConstraint,
    text,
    Integer,
    Index
)

from internal.extension.database_extension import db


class UploadFile(db.Model):
    """上传文件表"""
    __tablename__ = "upload_file"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_upload_file_id"),
        Index("idx_upload_file_account_id", "account_id"),
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID, nullable=False,
                        server_default=text('uuid_generate_v4()'))  # 账号ID，非空，默认生成一个UUID（实际业务中应由外键传入，此处按规范添加默认值）
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 原始文件名
    key = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 云端存储路径
    # size = Column(BigInteger, nullable=False, server_default=text("'0'::bigint"))  # 文件大小（字节），使用BigInteger
    size = Column(Integer, nullable=False, server_default=text("0"))
    extension = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 扩展名
    mime_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # MIME类型
    hash = Column(String(255), nullable=False, server_default=text("''::character varying"))  # 文件哈希值
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
