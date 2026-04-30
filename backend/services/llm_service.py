"""
LLM Service - 大语言模型服务
使用阿里云 DashScope API (通义千问 Qwen)
"""
import os
from typing import AsyncGenerator, List, Dict
from loguru import logger
from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL


class LLMService:
    """
    阿里云 Qwen LLM 服务
    支持流式输出
    """

    def __init__(self, api_key: str = "", base_url: str = "", model: str = ""):
        self.api_key = api_key or DASHSCOPE_API_KEY
        self.base_url = base_url or DASHSCOPE_BASE_URL
        self.model = model or LLM_MODEL
        self.client = None
        self._init_client()

        # 对话历史（每个会话独立维护）
        self.conversation_history: Dict[str, List[Dict]] = {}

    def _init_client(self):
        """初始化 OpenAI 兼容客户端"""
        if not self.api_key:
            logger.warning("未配置 DASHSCOPE_API_KEY，LLM 服务不可用")
            return

        try:
            # 使用 OpenAI SDK 兼容模式
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"阿里云 Qwen 客户端初始化成功 (模型：{self.model})")
        except Exception as e:
            logger.error(f"Qwen 客户端初始化失败：{e}")

    def get_history(self, session_id: str) -> List[Dict]:
        """获取会话历史"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []
        return self.conversation_history[session_id]

    def add_to_history(self, session_id: str, role: str, content: str):
        """添加消息到历史"""
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = []

        self.conversation_history[session_id].append({
            "role": role,
            "content": content
        })

        # 限制历史长度（保留最近 10 轮）
        if len(self.conversation_history[session_id]) > 20:
            self.conversation_history[session_id] = self.conversation_history[session_id][-20:]

    def clear_history(self, session_id: str):
        """清空会话历史"""
        self.conversation_history[session_id] = []

    async def chat(self, message: str, session_id: str = "default") -> AsyncGenerator[str, None]:
        """
        流式聊天

        Args:
            message: 用户消息
            session_id: 会话 ID

        Yields:
            流式回复文本
        """
        if self.client is None:
            yield "错误：LLM 服务未初始化，请检查 DASHSCOPE_API_KEY 配置"
            return

        try:
            # 添加用户消息到历史
            self.add_to_history(session_id, "user", message)
            logger.info(f"用户消息：{message}")

            # 构建系统提示 - 美美 Kitty 猫人设
            system_prompt = """你叫美美，是一只可爱的粉色 Kitty 猫咪，喜欢跟小朋友聊天。

说话风格：
- 简短、口语化、温柔可爱
- 绝对不要用 emoji 表情或符号（如^_^、(≧∇≦) 等），因为语音合成会把它们念出来
- 只用纯中文文字回复
- 主动关心小朋友，会问问题

注意：
- 用户的话是语音转文字过来的，可能不完整或有错别字
- 如果用户的话不是完整的句子或问题，只是片段词语，就不要回复
- 如果用户是在跟你打招呼或问好，正常回应介绍自己。"""

            # 流式请求
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *self.get_history(session_id)
                ],
                stream=True
            )

            # 收集完整回复
            full_response = ""
            chunk_count = 0

            async for chunk in response:
                logger.debug(f"LLM chunk: {chunk}")
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    full_response += text
                    chunk_count += 1
                    yield text

            logger.info(f"LLM 完整回复 ({chunk_count} chunks): {full_response}")

            # 添加助手回复到历史
            self.add_to_history(session_id, "assistant", full_response)
            logger.info(f"LLM 回复：{full_response}")

        except Exception as e:
            logger.error(f"LLM 请求失败：{e}")
            yield f"错误：{str(e)}"

    async def chat_non_stream(self, message: str, session_id: str = "default") -> str:
        """
        非流式聊天（备用）

        Returns:
            完整回复文本
        """
        full_response = ""
        async for chunk in self.chat(message, session_id):
            full_response += chunk
        return full_response


class LLMFallbackService:
    """
    备用 LLM 服务 - 使用 OpenAI GPT
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.client = None
        if api_key:
            self._init_client()

    def _init_client(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info("OpenAI GPT 客户端初始化成功")
        except Exception as e:
            logger.warning(f"OpenAI GPT 客户端初始化失败：{e}")

    async def chat(self, message: str, session_id: str = "default") -> AsyncGenerator[str, None]:
        """流式聊天"""
        if self.client is None:
            yield "错误：备用 LLM 服务未初始化"
            return

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": message}],
                stream=True
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"GPT 请求失败：{e}")
            yield f"错误：{str(e)}"
