import asyncio
from datetime import datetime, timedelta
from typing import Dict
import logging
from pkg.plugin.context import register, handler, llm_func, BasePlugin, APIHost, EventContext
from pkg.plugin.events import *
from .reminder import ReminderManager
from .time_parser import TimeParser
from .handlers import MessageHandler

@register(name="QReminderPlugin", description="智能定时提醒插件，支持设置单次和重复提醒，基于自然语言理解", version="1.2.0", author="Wedjat98")
class QReminderPlugin(BasePlugin):
    def __init__(self, host: APIHost):
        self.host = host
        self.reminder_manager = ReminderManager()
        self.time_parser = TimeParser()
        self.message_handler = MessageHandler(self.reminder_manager, self.time_parser)
        self.adapter_cache = None
        self.last_adapter_check = None
        
    async def initialize(self):
        """异步初始化，加载已保存的提醒"""
        # 加载已保存的提醒
        await self.reminder_manager.load_reminders()
        
        # 恢复所有活跃的提醒任务
        restored_count = 0
        for reminder_id, reminder_data in self.reminder_manager.reminders.items():
            if reminder_data.get('active', True):
                # 检查提醒时间是否还未到
                target_time = datetime.fromisoformat(reminder_data['target_time'])
                if target_time > datetime.now():
                    await self._schedule_reminder(reminder_id, reminder_data)
                    restored_count += 1
                else:
                    self.ap.logger.info(f"⏰ 跳过已过期的提醒: {reminder_data['content']}")
        
        self.ap.logger.info(f"🚀 提醒插件初始化完成，恢复了 {restored_count} 个活跃提醒任务")

    async def _get_available_adapter(self):
        """获取可用的适配器，带缓存机制"""
        try:
            # 如果缓存存在且在5分钟内，直接返回
            if self.adapter_cache and self.last_adapter_check:
                if (datetime.now() - self.last_adapter_check).seconds < 300:
                    return self.adapter_cache
            
            # 重新获取适配器
            adapters = self.host.get_platform_adapters()
            if adapters and len(adapters) > 0:
                self.adapter_cache = adapters[0]
                self.last_adapter_check = datetime.now()
                self.ap.logger.debug(f"✅ 成功获取适配器: {type(self.adapter_cache)}")
                return self.adapter_cache
            else:
                self.ap.logger.warning("⚠️ 没有找到可用的平台适配器")
                return None
                
        except Exception as e:
            self.ap.logger.error(f"❌ 获取适配器时出错: {e}")
            return None

    @llm_func("set_reminder")
    async def set_reminder_llm(self, query, content: str, time_description: str, repeat_type: str = "不重复"):
        """AI函数调用接口：设置提醒
        当用户说要设置提醒、定时任务等时调用此函数
        
        Args:
            content(str): 提醒内容，例如："开会"、"吃药"、"买菜"等
            time_description(str): 时间描述，支持自然语言，例如："30分钟后"、"明天下午3点"、"今晚8点"等
            repeat_type(str): 重复类型，可选值："不重复"、"每天"、"每周"、"每月"
            
        Returns:
            str: 设置结果信息
        """
        try:
            # 移除可能的干扰词
            time_description = time_description.replace("设置", "").replace("这里", "").strip()
            
            # 自动检测重复类型
            if "每天" in time_description and repeat_type == "不重复":
                repeat_type = "每天"
                time_description = time_description.replace("每天", "")
            elif "每周" in time_description and repeat_type == "不重复":
                repeat_type = "每周"
                time_description = time_description.replace("每周", "")
            elif "每月" in time_description and repeat_type == "不重复":
                repeat_type = "每月"
                time_description = time_description.replace("每月", "")
            
            # 获取目标信息
            target_info = {
                "target_id": str(query.launcher_id),
                "sender_id": str(query.sender_id), 
                "target_type": str(query.launcher_type).split(".")[-1].lower(),
            }
            
            self.ap.logger.debug(f"解析时间描述: '{time_description}'")
            
            # 解析时间
            target_time = await self.time_parser.parse_time_natural(time_description)
            if not target_time:
                suggestions = [
                    "• 相对时间：30分钟后、2小时后、3天后",
                    "• 具体日期：明天下午3点、后天晚上8点",  
                    "• 星期时间：本周六晚上9点、下周一上午10点",
                    "• 标准格式：2025-06-08 15:30"
                ]
                return f"⚠️ 无法理解时间 '{time_description}'\n\n支持的格式示例：\n" + "\n".join(suggestions)

            # 检查时间是否已过
            if target_time <= datetime.now():
                return "⚠️ 设置的时间已经过去了，请重新设置！"

            # 生成提醒ID
            reminder_id = f"{target_info['sender_id']}_{int(datetime.now().timestamp())}"
            
            # 创建提醒数据
            reminder_data = {
                'id': reminder_id,
                'sender_id': target_info['sender_id'],
                'target_id': target_info['target_id'],
                'target_type': target_info['target_type'],
                'content': content,
                'target_time': target_time.isoformat(),
                'repeat_type': repeat_type,
                'active': True,
                'created_at': datetime.now().isoformat()
            }

            # 保存提醒
            self.reminder_manager.add_reminder(reminder_id, reminder_data)
            await self.reminder_manager.save_reminders()

            # 安排提醒任务
            await self._schedule_reminder(reminder_id, reminder_data)

            # 返回确认信息，包含星期信息
            time_str_formatted = target_time.strftime("%Y年%m月%d日 %H:%M")
            weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
            weekday = weekday_names[target_time.weekday()]
            repeat_info = f"\n🔄 重复：{repeat_type}" if repeat_type != "不重复" else ""
            
            self.ap.logger.info(f"🎯 用户 {target_info['sender_id']} 设置提醒成功: {content} 在 {time_str_formatted}")
            
            return f"✅ 提醒设置成功！\n📅 时间：{time_str_formatted} ({weekday})\n📝 内容：{content}{repeat_info}"

        except Exception as e:
            self.ap.logger.error(f"❌ 设置提醒失败: {e}")
            import traceback
            self.ap.logger.error(traceback.format_exc())
            return f"❌ 设置提醒失败：{str(e)}"

    @handler(PersonNormalMessageReceived)
    async def person_normal_message_received(self, ctx: EventContext):
        await self.message_handler.handle_message(ctx, False)

    @handler(GroupNormalMessageReceived)
    async def group_normal_message_received(self, ctx: EventContext):
        await self.message_handler.handle_message(ctx, True)

    async def _schedule_reminder(self, reminder_id: str, reminder_data: Dict):
        """安排提醒任务"""
        try:
            # 计算延迟时间
            target_time = datetime.fromisoformat(reminder_data['target_time'])
            delay = (target_time - datetime.now()).total_seconds()
            
            if delay <= 0:
                self.ap.logger.warning(f"⚠️ 提醒时间已过: {reminder_data['content']}")
                return
                
            # 创建任务
            task = asyncio.create_task(self._reminder_task(reminder_id, delay))
            self.reminder_manager.add_task(reminder_id, task)
            
        except Exception as e:
            self.ap.logger.error(f"❌ 安排提醒任务失败: {e}")

    async def _reminder_task(self, reminder_id: str, delay: float):
        """提醒任务"""
        try:
            # 等待指定时间
            await asyncio.sleep(delay)
            
            # 获取提醒数据
            reminder_data = self.reminder_manager.get_reminder(reminder_id)
            if not reminder_data:
                return
                
            # 发送提醒消息
            await self._send_reminder_message(reminder_data)
            
            # 处理重复提醒
            if reminder_data.get('repeat_type') != "不重复":
                await self._handle_repeat_reminder(reminder_id, reminder_data)
            else:
                # 删除一次性提醒
                self.reminder_manager.remove_reminder(reminder_id)
                await self.reminder_manager.save_reminders()
                
        except asyncio.CancelledError:
            self.ap.logger.info(f"⏸️ 提醒任务已取消: {reminder_id}")
        except Exception as e:
            self.ap.logger.error(f"❌ 提醒任务执行失败: {e}")

    async def _send_reminder_message(self, reminder_data: Dict):
        """发送提醒消息"""
        try:
            # 获取适配器
            adapter = await self._get_available_adapter()
            if not adapter:
                self.ap.logger.error("❌ 无法发送提醒：没有可用的适配器")
                return
                
            # 构建消息内容
            content = reminder_data['content']
            target_time = datetime.fromisoformat(reminder_data['target_time'])
            time_str = target_time.strftime("%Y-%m-%d %H:%M")
            
            # 根据目标类型发送消息
            target_type = reminder_data['target_type']
            target_id = reminder_data['target_id']
            
            if target_type == "person":
                await adapter.send_person_message(target_id, f"⏰ 提醒：{content}\n⏱️ 时间：{time_str}")
            elif target_type == "group":
                await adapter.send_group_message(target_id, f"⏰ 提醒：{content}\n⏱️ 时间：{time_str}")
            else:
                self.ap.logger.warning(f"⚠️ 未知的目标类型: {target_type}")
                
        except Exception as e:
            self.ap.logger.error(f"❌ 发送提醒消息失败: {e}")

    async def _handle_repeat_reminder(self, reminder_id: str, reminder_data: Dict):
        """处理重复提醒"""
        try:
            repeat_type = reminder_data.get('repeat_type')
            target_time = datetime.fromisoformat(reminder_data['target_time'])
            
            # 计算下一次提醒时间
            if repeat_type == "每天":
                next_time = target_time + timedelta(days=1)
            elif repeat_type == "每周":
                next_time = target_time + timedelta(days=7)
            elif repeat_type == "每月":
                # 获取下个月的同一天
                if target_time.month == 12:
                    next_time = target_time.replace(year=target_time.year + 1, month=1)
                else:
                    next_time = target_time.replace(month=target_time.month + 1)
            else:
                return
                
            # 更新提醒时间
            reminder_data['target_time'] = next_time.isoformat()
            self.reminder_manager.update_reminder(reminder_id, reminder_data)
            await self.reminder_manager.save_reminders()
            
            # 安排下一次提醒
            await self._schedule_reminder(reminder_id, reminder_data)
            
        except Exception as e:
            self.ap.logger.error(f"❌ 处理重复提醒失败: {e}")

    def __del__(self):
        """清理资源"""
        # 取消所有运行中的任务
        for task in self.reminder_manager.running_tasks.values():
            task.cancel() 