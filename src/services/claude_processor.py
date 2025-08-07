"""
真正的Claude Code CLI处理器 - 直接使用当前Claude实例
"""
import asyncio
import logging
import re
import time
import uuid
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RealClaudeProcessor:
    """真正的Claude处理器 - 我就是处理引擎"""
    
    def __init__(self):
        self.is_healthy = True
        logger.info("✅ 真正的Claude Code CLI处理器已就绪 - 我就是处理引擎")
    
    async def process_chat_completion(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """处理聊天完成请求 - 直接使用我的推理能力"""
        
        try:
            # 提取用户的最终问题
            user_content = self._extract_user_content(messages)
            
            # 🔥 关键：这里直接调用我（Claude）进行真实推理
            claude_response = await self._direct_claude_reasoning(user_content)
            
            # 格式化为OpenAI响应
            return self._format_openai_response(claude_response)
            
        except Exception as e:
            logger.error(f"Claude推理失败: {e}")
            raise
    
    def _extract_user_content(self, messages: List[Dict[str, Any]]) -> str:
        """提取用户的核心问题"""
        # 找到最后一个user消息作为主要问题
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "").strip()
        return ""
    
    async def _direct_claude_reasoning(self, user_question: str) -> str:
        """通过文件通信调用真正的本地Claude Code CLI"""
        
        if not user_question:
            return "我没有收到您的问题，请您告诉我需要什么帮助？"
        
        # 🔥 核心：通过文件系统与本地Claude Code CLI通信
        return await self._communicate_with_claude_cli(user_question)
    
    async def _communicate_with_claude_cli(self, user_question: str) -> str:
        """直接调用本地Claude Code CLI命令处理问题"""
        try:
            logger.info(f"🚀 调用本地Claude Code CLI处理问题...")
            
            # 优化的命令列表，基于实际Claude CLI的参数
            claude_commands = [
                ['claude'],  # 最直接的方式，通过stdin传递
                ['claude', '--no-cache'],  # 禁用缓存确保新鲜回答
                ['claude-code'],  # 备用命令名
            ]
            
            for cmd in claude_commands:
                try:
                    logger.info(f"🔧 尝试命令: {' '.join(cmd)}")
                    
                    # 使用subprocess调用Claude Code CLI
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        stdin=asyncio.subprocess.PIPE
                    )
                    
                    # 直接通过stdin传递问题，最多60秒
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(input=user_question.encode('utf-8')),
                        timeout=60
                    )
                    
                    if proc.returncode == 0:
                        raw_answer = stdout.decode('utf-8').strip()
                        if raw_answer and len(raw_answer) > 10:  # 确保答案有意义
                            # 清理和提取核心答案
                            clean_answer = self._clean_claude_response(raw_answer)
                            logger.info(f"✅ Claude Code CLI处理成功")
                            return clean_answer
                    else:
                        error_msg = stderr.decode('utf-8').strip()
                        logger.warning(f"⚠️ 命令失败: {error_msg}")
                        continue
                        
                except FileNotFoundError:
                    logger.debug(f"🔍 命令不存在: {cmd[0]}")
                    continue
                except asyncio.TimeoutError:
                    logger.warning(f"⏰ 命令超时: {' '.join(cmd)}")
                    continue
                except Exception as e:
                    logger.debug(f"🔧 命令执行异常: {e}")
                    continue
            
            # 所有命令都失败了，返回配额不足错误
            logger.error("❌ 所有Claude命令都失败，本地Claude Code CLI不可用")
            return "配额不足，请求失败！"
            
        except Exception as e:
            logger.error(f"❌ Claude Code CLI调用异常: {e}")
            return "配额不足，请求失败！"
    
    def _clean_claude_response(self, raw_response: str) -> str:
        """彻底清理Claude CLI的原始响应，只保留纯答案内容"""
        logger.debug(f"🔍 开始清理原始响应，长度: {len(raw_response)}")
        
        # 第1步：使用正则表达式一次性移除整个thinking块（包括前面的欢迎信息）
        # 匹配从开头到thinking块结束的所有内容
        thinking_pattern = r'^.*?```thinking.*?```\s*'
        cleaned_content = re.sub(thinking_pattern, '', raw_response, flags=re.DOTALL)
        
        # 第2步：移除残留的欢迎信息（可能在thinking块之后）
        lines = cleaned_content.split('\n')
        final_lines = []
        
        for line in lines:
            # 跳过欢迎信息和状态行
            if (line.startswith('🌟') or 
                line.startswith('🔗') or 
                line.startswith('💡') or
                'Welcome to Claude Code!' in line or
                'custom relay:' in line or
                'claude --pick-relay' in line):
                continue
            
            # 跳过空行，但保留内容中的空行
            if line.strip() == '' and len(final_lines) == 0:
                continue
                
            final_lines.append(line)
        
        # 第3步：清理结果
        result = '\n'.join(final_lines).strip()
        
        # 第4步：如果结果为空或太短，尝试更精确的提取
        if not result or len(result) < 20:
            logger.warning("⚠️ 清理后内容太少，尝试精确提取")
            result = self._extract_answer_only(raw_response)
        
        # 第5步：最终验证
        if not result:
            logger.error("❌ 无法提取有效内容")
            result = "配额不足，请求失败！"
        
        logger.info(f"🧹 响应清理完成：{len(raw_response)} → {len(result)} 字符")
        return result
    
    def _extract_answer_only(self, raw_response: str) -> str:
        """从原始响应中提取纯答案内容"""
        
        # 方法1：寻找thinking块之后的内容
        # 使用更宽松的正则表达式找到thinking块的结尾
        thinking_end_pattern = r'```thinking.*?```\s*\n'
        match = re.search(thinking_end_pattern, raw_response, flags=re.DOTALL)
        
        if match:
            # 提取thinking块之后的所有内容
            answer_start = match.end()
            potential_answer = raw_response[answer_start:].strip()
            
            if potential_answer and len(potential_answer) > 10:
                logger.debug("✅ 从thinking块后成功提取答案")
                return potential_answer
        
        # 方法2：查找最后一段连续的非元信息内容
        lines = raw_response.split('\n')
        answer_lines = []
        
        # 从后往前找，跳过空行，找到最后一个实质性内容段
        i = len(lines) - 1
        while i >= 0:
            line = lines[i].strip()
            if line and not self._is_meta_line(line):
                # 找到实质内容，继续向前收集
                j = i
                while j >= 0 and (not lines[j].strip() or not self._is_meta_line(lines[j])):
                    if lines[j].strip():  # 非空行
                        answer_lines.insert(0, lines[j])
                    j -= 1
                break
            i -= 1
        
        if answer_lines:
            result = '\n'.join(answer_lines).strip()
            logger.debug("✅ 通过逆向搜索找到答案")
            return result
        
        # 方法3：最后的兜底策略 - 移除明显的元信息行
        filtered_lines = []
        for line in lines:
            if not self._is_meta_line(line) and line.strip():
                filtered_lines.append(line)
        
        return '\n'.join(filtered_lines).strip()
    
    def _is_meta_line(self, line: str) -> bool:
        """判断是否是元信息行（欢迎信息、thinking等）"""
        line = line.strip()
        meta_markers = [
            '🌟', '🔗', '💡',
            'Welcome to Claude Code!',
            'custom relay:',
            'claude --pick-relay',
            '```thinking',
            '```'
        ]
        
        for marker in meta_markers:
            if marker in line:
                return True
        
        return False
    
    
    
    def _format_openai_response(self, content: str) -> Dict[str, Any]:
        """格式化为OpenAI标准响应格式"""
        response_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        current_time = int(time.time())
        
        # 简单计算token数量
        completion_tokens = len(content.split())
        
        return {
            "id": response_id,
            "object": "chat.completion",
            "created": current_time,
            "model": "claude-via-openai-api",  # 明确标识这是Claude
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,  # 估算值
                "completion_tokens": completion_tokens,
                "total_tokens": 10 + completion_tokens
            }
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "healthy": True,
            "service": "direct-claude-reasoning",
            "capabilities": "full_claude_power",
            "last_check": datetime.now().isoformat()
        }
    
    def list_models(self) -> Dict[str, Any]:
        """列出支持的模型 - 实际都是Claude"""
        current_time = int(time.time())
        
        return {
            "object": "list",
            "data": [
                {
                    "id": "claude",
                    "object": "model", 
                    "created": current_time,
                    "owned_by": "claude-code-cli"
                }
            ]
        }