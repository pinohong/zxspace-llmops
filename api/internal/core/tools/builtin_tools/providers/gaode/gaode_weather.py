#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time       : 2026/7/2 14:07
@Author     : 歌白
@File       : gaode_weather.py
"""
import json
import os
from typing import Any
from typing import Type

import requests
from langchain.tools import BaseTool
from langchain_core.pydantic_v1 import BaseModel, Field

from internal.lib.helper import add_attribute


class GaodeWeatherArgsSchema(BaseModel):
    city: str = Field(description="需要查询天气预报目标城市，例如：上海")


class GaodeWeatherTool(BaseTool):
    """根据传入的成名查询天气"""
    name = "gaode_weather"
    description = "当你想询问或与天气相关的问题时的工具"
    args_schema: Type[BaseModel] = GaodeWeatherArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """运行工具获取对应的天气预报"""
        try:
            # 1.获取高德API密钥，如果没有则抛出错误
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德开发平台密钥未配置"
            # 2.提取传递的城市名字并查询行政编码
            city = kwargs.get('city', "")
            session = requests.session()
            api_domain = "https://restapi.amap.com/v3/"
            city_response = session.request(
                method="GET",
                url=f"{api_domain}config/district?key={gaode_api_key}&keywords={city}&subdistrict=0&extensions=all&",
                headers={
                    "Content-Type": "application/json;charset=utf-8"
                }
            )
            city_response.raise_for_status()

            city_json = city_response.json()

            # 3.提取行政编码调用天气预报接口查询天气
            if city_json.get('info') == "OK":
                adcode = city_json["districts"][0]["adcode"]
                # 4.根据得到的adcode调用高德天气预报接口获取数据
                weather_response = session.request(
                    method="GET",
                    url=f"{api_domain}weather/weatherInfo?key={gaode_api_key}&city={adcode}&output=json&extensions=all",
                )
                weather_response.raise_for_status()
                weather_json = weather_response.json()
                if weather_json.get("info") == "OK":
                    # 5.返回最后的结果字符串
                    return json.dumps(weather_json)
            session.close()
            return f"获取{kwargs.get('city')}天气失败"
            # 4.整合天气预报信息并返回
        except Exception as e:
            print(e)
            return f"获取{kwargs.get('city')}天气预报失败"


@add_attribute("args_schema", GaodeWeatherArgsSchema)
def gaode_weather(**kwargs) -> BaseTool:
    return GaodeWeatherTool()
