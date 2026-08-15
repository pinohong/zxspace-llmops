#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/30 16:49
@Author     : 歌白
@File       : app_config_service.py
"""
from dataclasses import dataclass
from typing import Any, Union
from uuid import UUID

from flask import request
from injector import inject
from langchain_core.tools import BaseTool

from internal.core.language_model import LanguageModelManager
from internal.core.language_model.entities.model_entity import ModelParameterType
from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.workflow_entity import WorkflowStatus
from internal.lib.helper import datetime_to_timestamp, get_value_type
from internal.model import (
    App,
    ApiTool,
    Dataset,
    AppConfigVersion,
    AppConfig,
    AppDatasetJoin,
    Workflow,
)
from pkg.my_sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class AppConfigService(BaseService):
    """应用配置服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager
    language_model_manager: LanguageModelManager

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """根据传递的应用获取该应用的草稿配置"""

        # 1.提取应用的草稿配置
        draft_app_config = app.draft_app_config

        # 2.校验model_config信息，如果使用了不存在的提供者或者模型，则使用默认值（宽松校验）
        validate_model_config = self._process_and_validate_model_config(draft_app_config.model_config)
        if draft_app_config.model_config != validate_model_config:
            self.update(draft_app_config, model_config=validate_model_config)

        # 3.循环遍历工具列表删除已经被删除的工具信息
        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        # 4.如果校验后的工具列表和原始草稿不一致（有工具被剔除了），需要把清理后的列表写回数据库
        if draft_app_config.tools != validate_tools:
            # 5.更新草稿配置中的 tools 字段，同步清理掉已删除工具的引用
            self.update(draft_app_config, tools=validate_tools)

        # 5.判断是否存在已删除的知识库，如果存在则更新
        datasets, validate_datasets = self._process_and_validate_datasets(draft_app_config.datasets)

        # 6.如果存在已删除的知识库（筛选后的列表比原始短），更新草稿配置，剔除无效引用
        if set(validate_datasets) != set(draft_app_config.datasets):
            self.update(draft_app_config, datasets=validate_datasets)

        # 7.校验是否存在已删除的知识库，如果存在则更新。
        workflows, validate_workflows = self._process_and_validate_workflows(draft_app_config.workflows)
        if set(validate_workflows) != set(draft_app_config.workflows):
            self.update(draft_app_config, workflows=validate_workflows)

        # 9.将草稿配置的各个字段组装成字典返回给前端
        return self._process_and_transformer_app_config(
            validate_model_config,
            tools,
            workflows,
            datasets,
            draft_app_config
        )

    def get_app_config(self, app: App) -> dict[str, Any]:
        """根据传递的应用获取该应用的运行配置"""
        # 1.提取应用的草稿配置
        app_config = app.app_config

        # 2.校验model_config，如果运行时配置里的model_config发生变化则进行更新
        validate_model_config = self._process_and_validate_model_config(app_config.model_config)
        if app_config.model_config != validate_model_config:
            self.update(app_config, model_config=validate_model_config)

        # 3.循环遍历工具列表删除已经被删除的工具信息
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 4.如果校验后的工具列表和原始草稿不一致（有工具被剔除了），需要把清理后的列表写回数据库
        if app_config.tools != validate_tools:
            # 5.更新草稿配置中的 tools 字段，同步清理掉已删除工具的引用
            self.update(app_config, tools=validate_tools)

        # 6.判断是否存在已删除的知识库，如果存在则更新
        app_dataset_joins = app_config.app_dataset_joins
        origin_datasets = [str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins]
        datasets, validate_datasets = self._process_and_validate_datasets(origin_datasets)

        # 7.如果存在已删除的知识库（筛选后的列表比原始短），更新草稿配置，剔除无效引用
        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(AppDatasetJoin.dataset_id == dataset_id)

        # 8.校验工作流列表对应的数据
        workflows, validate_workflows = self._process_and_validate_workflows(app_config.workflows)
        if set(validate_workflows) != set(app_config.workflows):
            self.update(app_config, workflows=validate_workflows)

        # 9.将草稿配置的各个字段组装成字典返回给前端
        return self._process_and_transformer_app_config(
            validate_model_config,
            tools,
            workflows,
            datasets,
            app_config
        )

    @classmethod
    def _process_and_transformer_app_config(
            cls,
            model_config: dict[str, Any],
            tools: list[dict],
            workflows: list[dict],
            datasets: list[dict],
            app_config: Union[AppConfig, AppConfigVersion]
    ) -> dict[str, Any]:
        """根据传递的插件列表，工作流列表，知识库列表以及应用配置创建字典信息"""
        return {
            "id": str(app_config.id),
            "model_config": model_config,  # LLM 模型配置（模型名、温度等）
            "dialog_round": app_config.dialog_round,  # 对话轮次限制
            "preset_prompt": app_config.preset_prompt,  # 预设提示词
            "tools": tools,  # 经过校验+组装的工具列表
            "workflows": workflows,  # 工作流列表（预留）
            "datasets": datasets,  # 经过校验+组装的知识库列表
            "retrieval_config": app_config.retrieval_config,  # 检索配置
            "long_term_memory": app_config.long_term_memory,  # 长期记忆配置
            "opening_statement": app_config.opening_statement,  # 开场白
            "opening_questions": app_config.opening_questions,  # 开场推荐问题
            "speech_to_text": app_config.speech_to_text,  # 语音转文本配置
            "text_to_speech": app_config.text_to_speech,  # 文本转语音配置
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,  # 审核配置
            "updated_at": datetime_to_timestamp(app_config.updated_at),
            "created_at": datetime_to_timestamp(app_config.created_at),
        }

    def get_langchain_tools_by_tools_config(self, tools_config: list[dict]) -> list[BaseTool]:
        """根据传递的工具配置列表获取langchain工具列表"""
        tools = []
        for tool in tools_config:
            # 2.根据不同的工具类型执行不同的操作
            if tool["type"] == "builtin_tool":
                # 3.内置工具，通过builtin_provider_manager获取工具实例
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"],
                )

                if not builtin_tool:
                    continue
                tools.append(builtin_tool(**tool["tool"]["params"]))
            else:
                # 4.API工具,首先根据id找到ApiTool记录，
                api_tool = self.get(ApiTool, tool["tool"]["id"])
                if not api_tool:
                    continue
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            method=api_tool.method,
                            description=api_tool.description,
                            headers=api_tool.provider.headers,
                            parameters=api_tool.parameters
                        )
                    )
                )

        return tools

    def get_langchain_tools_by_workflow_ids(self, workflow_ids: list[UUID]) -> list[BaseTool]:
        """根据传递的工作流配置列表获取langchain工作列表"""
        # 1.根据传递的工作流id查询工作流记录信息
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(workflow_ids),
            Workflow.status == WorkflowStatus.PUBLISHED,
        ).all()

        # 2.循环遍历所有工作流记录列表
        workflows = []
        for workflow_record in workflow_records:
            try:
                # 3.创建工作流工具
                workflow_tool = WorkflowTool(workflow_config=WorkflowConfig(
                    account_id=workflow_record.account_id,
                    name=f"wf_{workflow_record.tool_call_name}",
                    description=workflow_record.description,
                    nodes=workflow_record.graph.get("nodes", []),
                    edges=workflow_record.graph.get("edges", []),
                ))
                workflows.append(workflow_tool)
            except Exception:
                continue

        return workflows

    def _process_and_validate_tools(self, origin_tools: list[dict]) -> tuple[list[dict], list[dict]]:
        """根据传递的原始工具信息进行处理校验"""
        validate_tools = []
        tools = []

        for tool in origin_tools:
            if tool["type"] == "builtin_tool":
                provider = self.builtin_provider_manager.get_provider(tool["provider_id"])
                if not provider:
                    continue

                tool_entity = provider.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue

                param_keys = set([param.name for param in tool_entity.params])
                params = tool["params"]
                if set(tool["params"].keys()) - param_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }

                validate_tools.append({**tool, "params": params})

                provider_entity = provider.provider_entity
                tools.append({
                    "type": "builtin_tool",
                    "provider": {
                        "id": provider_entity.name,
                        "name": provider_entity.name,
                        "label": provider_entity.label,
                        "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                        "description": provider_entity.description,
                    },
                    "tool": {
                        "name": tool_entity.name,
                        "label": tool_entity.label,
                        "description": tool_entity.description,
                        "params": tool["params"],
                    },
                })

            elif tool["type"] == "api_tool":
                tool_record = self.db.session.query(ApiTool).filter(
                    ApiTool.provider_id == tool["provider_id"],
                    ApiTool.name == tool["tool_id"],
                ).one_or_none()
                if not tool_record:
                    continue

                validate_tools.append(tool)

                provider = tool_record.provider
                tools.append({
                    "type": "api_tool",
                    "provider": {
                        "id": str(provider.id),
                        "name": provider.name,
                        "label": provider.name,
                        "icon": provider.icon,
                        "description": provider.description,
                    },
                    "tool": {
                        "id": str(tool_record.id),
                        "name": tool_record.name,
                        "label": tool_record.name,
                        "description": tool_record.description,
                        "params": {}
                    }
                })

        return tools, validate_tools

    def _process_and_validate_datasets(self, origin_datasets: list[dict]) -> tuple[list[dict], list[dict]]:
        """根据传递的知识库并返回知识库配置与校验后的数据"""
        # 1.校验知识库配置列表，如果引用了不存在的/被删除的知识库，则需要剔除数据并更新，同时获取知识库的额外信息
        datasets = []  # 最终返回给前端的知识库展示列表
        dataset_records = self.db.session.query(Dataset).filter(
            Dataset.id.in_(origin_datasets)  # 用 IN 查询一次性查出所有引用的知识库
        ).all()
        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}
        dataset_sets = set(dataset_dict.keys())  # 实际存在于数据库中的知识库 id 集合

        # 2.按草稿中的原始顺序，筛选出仍然存在的知识库 id（保留顺序是为了保持用户排好的优先级）
        validate_datasets = [dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets]

        # 3.遍历仍然存在的知识库 id，组装展示信息
        for dataset_id in validate_datasets:
            dataset = dataset_dict.get(str(dataset_id))  # 从映射中取出 Dataset 对象
            datasets.append({
                "id": str(dataset_id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description,
            })

        return datasets, validate_datasets

    def _process_and_validate_model_config(self, origin_model_config: dict[str, Any]) -> dict[str, Any]:
        """根据传递的模型配置处理并校验，随后返回校验后的信息"""
        # 1.判断model_config是否为字典，如果不是则直接返回默认值
        if not isinstance(origin_model_config, dict):
            return DEFAULT_APP_CONFIG["model_config"]

        # 2.提取origin_model_config中provider、model、parameters对应的信息
        model_config = {
            "provider": origin_model_config.get("provider", ""),
            "model": origin_model_config.get("model", ""),
            "parameters": origin_model_config.get("parameters", {}),
        }

        # 3.判断provider是否存在、类型是否正确，如果不符合规则则返回默认值
        if not model_config["provider"] or not isinstance(model_config["provider"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        provider = self.language_model_manager.get_provider(model_config["provider"])
        if not provider:
            return DEFAULT_APP_CONFIG["model_config"]

        # 4.判断model是否存在、类型是否正确，如果不符合则返回默认值
        if not model_config["model"] or not isinstance(model_config["model"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        model_entity = provider.get_model_entity(model_config["model"])
        if not model_entity:
            return DEFAULT_APP_CONFIG["model_config"]

        # 5.判断parameters信息类型是否错误，如果错误则设置为默认值
        if not isinstance(model_config["parameters"], dict):
            model_config["parameters"] = {
                parameter.name: parameter.default for parameter in model_entity.parameters
            }

        # 6.剔除传递的多余的parameter，亦或者是少传递的参数使用默认值补上
        parameters = {}
        for parameter in model_entity.parameters:
            # 7.从model_config中获取参数值，如果不存在则设置为默认值
            parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

            # 8.判断参数是否必填
            if parameter.required:
                # 9.参数必填，则值不允许为None，如果为None则设置默认值
                if parameter_value is None:
                    parameter_value = parameter.default
                else:
                    # 10.值非空则校验数据类型是否正确，不正确则设置默认值
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            else:
                # 11.参数非必填，数据非空的情况下需要校验
                if parameter_value is not None:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default

            # 12.判断参数是否存在options，如果存在则数值必须在options中选择
            if parameter.options and parameter_value not in parameter.options:
                parameter_value = parameter.default

            # 13.参数类型为int/float，如果存在min/max时候需要校验
            if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                # 14.校验数值的min/max
                if (
                        (parameter.min and parameter_value < parameter.min)
                        or (parameter.max and parameter_value > parameter.max)
                ):
                    parameter_value = parameter.default

            parameters[parameter.name] = parameter_value

        # 15.完成数据校验，赋值parameters参数
        model_config["parameters"] = parameters

        return model_config

    def _process_and_validate_workflows(self, origin_workflows: list[UUID]) -> tuple[list[dict], list[UUID]]:
        """根据传递的工作流列表并返回工作流配置和校验后的数据"""
        # 1.校验工作流配置列表，如果引用了不存在/被删除的工作流，则需要提出数据并更新，同时获取工作流的额外信息
        workflows = []
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(origin_workflows),
            Workflow.status == WorkflowStatus.PUBLISHED,
        ).all()
        workflow_dict = {str(workflow_record.id): workflow_record for workflow_record in workflow_records}
        workflow_sets = set(workflow_dict.keys())

        # 2.计算存在的工作流id列表，为了保留原始顺序，使用列表循环的方式来判断
        validate_workflows = [workflow_id for workflow_id in origin_workflows if workflow_id in workflow_sets]

        # 3.循环获取工作流数据
        for workflow_id in validate_workflows:
            workflow = workflow_dict.get(str(workflow_id))
            workflows.append({
                "id": str(workflow.id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description,
            })

        return workflows, validate_workflows
