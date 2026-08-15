#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/02/01 2:40
@Author  : thezehui@gmail.com
@File    : chat.py
"""
import os
from typing import Tuple

import tiktoken
from langchain_openai.chat_models.base import BaseChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(BaseChatOpenAI, BaseLanguageModel):
    """娣卞害姹傜储澶ц瑷€妯″瀷鍩虹被"""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base=os.getenv("DEEPSEEK_API_BASE"),
            **kwargs
        )

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """閲嶅啓鏈堜箣鏆楅潰鑾峰彇缂栫爜妯″瀷鍚嶅瓧+妯″瀷鍑芥暟锛岃绫荤户鎵縊penAI锛岃瘝琛ㄦā鍨嬪彲浠ヤ娇鐢╣pt-3.5-turbo闃叉鍑洪敊"""
        # 1.灏咲eepSeek鐨勮瘝琛ㄦā鍨嬭缃负gpt-3.5-turbo
        model = "gpt-3.5-turbo"

        # 2.杩斿洖妯″瀷鍚嶅瓧+缂栫爜鍣?
        return model, tiktoken.encoding_for_model(model)
