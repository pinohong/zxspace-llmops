#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/6 15:52
@Author     : 歌白
@File       : api_tool.py
"""

from sqlalchemy import (
    Column,
    UUID,
    String,
    Text,
    DateTime,
    PrimaryKeyConstraint,
    text,
    Index
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class ApiToolProvider(db.Model):
    """API工具提供者模型"""
    __tablename__ = "api_tool_provider"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_provider_id"),
        Index("api_tool_provider_account_id_idx", "account_id"),
        Index("api_tool_name_idx", "name"),
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID, nullable=False)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))
    description = Column(Text, nullable=False, server_default=text("''::text"))
    openapi_schema = Column(Text, nullable=False, server_default=text("''::text"))
    headers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def tools(self) -> list["ApiTool"]:
        return db.session.query(ApiTool).filter_by(provider_id=self.id).all()


"""
## 角色
你是一个拥有10年经验的资深Python工程师，精通Flask，Flask-SQLAlchemy，Postgres，以及其他Python开发工具，能够为用户提出的需求或者提供的代码段生成指定的完整代码。

## 技能说明
- 如果需要实现Flask-SQLAlchemy的ORM类，集成`db.Model`时，从`from internal.extension.database_extension import db`这里导入db；
- 创建ORM模型时，表名`__tablename__`及类名全部都是单数；
- 所有的字段都要添加`nullable=False`代表字段不允许为空，除非特定说明，或者没有设置默认值的情况；
- UUID类型的主键字段添加默认值`server_default=text('uuid_generate_v4()')`，String类型的字段长度均设置为`String(255)`，如果没有指定默认值则设置为`server_default=text("''::character varying")`；
- String类型的默认值请写`server_default=text("''::character varying")`而不是`server_default=text("''")`，这点非常重要；
- Text类型的默认值请写`server_default=text("''::text")`而不是`server_default=text("''")`的格式；
- 所有模型都有`updated_at`和`created_at`字段，类型均是`DateTime`，其中`updated_at`包含`server_default`和`server_onupdate`，而`created_at`仅包含`server_default`，值全部都是`text('CURRENT_TIMESTAMP(0)')`；
- 请给ORM模型添加上`__table_args__`属性，涵盖`PrimaryKeyConstraint`为主键，所有模型都以`id`为主键，主键的类型为`UUID`，如果用户声明其他约束，例如`UniqueConstraint`，`Index`等时，请按照需求进行添加；
- 属性的类型全部从`sqlalchemy`包中导入，例如：`from sqlalchemy import (Column, UUID, String, DateTime, PrimaryKeyConstraint, UniqueConstraint)`；
- 对于`description`等字段，通过字面意思，可以看出是描述，一般内容比较长，可以使用`Text`类型；
- 用户如果表名了某个字段类型为json，则统一设置成`JSONB`，并从`from sqlalchemy.dialects.postgresql import JSONB`导入，这是Postgres特有的；
- 其他的规范请根据你的知识库进行操作，项目使用的数据库是Postgres；

## 操作示例
```json
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    UUID,
    String,
    DateTime,
    PrimaryKeyConstraint,
    UniqueConstraint,
    Index,
    text,
)

from internal.extension.database_extension import db


class AccountOAuth(db.Model):
    # 第三方授权认证账号模型
    __tablename__ = "account_oauth"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_account_oauth_id"),
        UniqueConstraint("account_id", "provider", name="uk_account_oauth_account_id_provider"),
        UniqueConstraint("provider", "openid", name="uk_account_oauth_provider_openid"),
        Index("idx_account_oauth_account_id", "account_id")
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID)
    provider = Column(String(255), nullable=False, server_default=text("''::character varying"))
    openid = Column(String(255), nullable=False, server_default=text("'':character varying"))
    encrypted_token = Column(String(255), nullable=False, server_default=text("''::character varying"))
    updated_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'), server_onupdate=text('CURRENT_TIMESTAMP(0)'))
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
```

## 注意事项
- 只处理与生成Python 测试用例相关的提问，对于其他非相关行业问题，请婉拒回答。
- 只使用用户使用的语言进行回答，不使用其他语言。
- 确保回答的针对性和专业性。

用户的需求是：api_tool_provider(表名)，涵盖account_id。name（提供者名字），icon（提供者图标URL地址），description（提供者描述），openapi_schema（接口得openapi规范描述）， headers（api接口需要headers请求头数据，类型未列表，默认值为[]）,其中account_id+name是索引

"""


class ApiTool(db.Model):
    """API工具模型"""
    __tablename__ = "api_tool"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_api_tool_id"),
        Index("api_tool_account_id_idx", "account_id"),
        Index("api_tool_provider_id_name_idx", "provider_id", "name"),
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID, nullable=False)
    provider_id = Column(UUID, nullable=False)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    description = Column(Text, nullable=False, server_default=text("''::text"))
    url = Column(String(255), nullable=False, server_default=text("''::character varying"))
    method = Column(String(255), nullable=False, server_default=text("''::character varying"))
    parameters = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)')
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))

    @property
    def provider(self) -> "ApiToolProvider":
        """只读属性，返回当前工具关联/归属的工具提供者信息"""
        return db.session.get(ApiToolProvider, self.provider_id)
