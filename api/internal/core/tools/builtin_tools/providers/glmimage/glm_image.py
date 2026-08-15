#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/2 14:38
@Author     : 歌白
@File       : glm_image.py
"""
import os
from typing import Optional

import dotenv
from langchain_core.callbacks import CallbackManagerForToolRun
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from zhipuai import ZhipuAI

from internal.lib.helper import add_attribute

dotenv.load_dotenv()


class GLMImageArgsSchema(BaseModel):
    query: str = Field(description="输入应该是生成图像的文本提示(prompt)")
    size: Optional[str] = Field(default=None, description="图片尺寸，可选：1024x1024, 1792x1024, 1024x1792")
    quality: Optional[str] = Field(default=None, description="图片质量，可选：standard, hd")
    style: Optional[str] = Field(default=None, description="图片风格，可选：vivid, natural")


# --- 自定义智谱AI文生图工具 ---
class GLMImageTool(BaseTool):
    name: str = "glm_image_generator"
    description: str = (
        "使用智谱AI的GLM-Image (CogView) 模型生成图像。"
        "当你需要画图、生成图像或处理视觉生成任务时调用该工具。"
        "该工具的输入是生成图像的文本提示。"
    )
    args_schema: type[BaseModel] = GLMImageArgsSchema

    size: str = "1024x1024"
    quality: Optional[str] = None
    style: Optional[str] = None
    watermark_enabled: bool = True

    def _run(
            self,
            query: str,
            size: Optional[str] = None,
            quality: Optional[str] = None,
            style: Optional[str] = None,
            run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        client = ZhipuAI(api_key=os.getenv("GLM_API_KEY"))

        response = client.images.generations(
            model="GLM-Image",
            prompt=query,
            size=size or self.size,
            quality=quality or self.quality,
            style=style or self.style,
            extra_body={"watermark_enabled": self.watermark_enabled},
        )

        if response.data and len(response.data) > 0:
            image_url = response.data[0].url
            return f"图片已成功生成，图片链接为: {image_url}"
        return "图片生成失败。"

    async def _arun(
            self,
            query: str,
            size: Optional[str] = None,
            quality: Optional[str] = None,
            style: Optional[str] = None,
            run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        return self._run(query, size=size, quality=quality, style=style, run_manager=run_manager)


@add_attribute('args_schema', GLMImageArgsSchema)
def glm_image(**kwargs) -> BaseTool:
    """返回GLM绘图工具"""
    return GLMImageTool(**kwargs)
