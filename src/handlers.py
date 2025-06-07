from datetime import datetime
from typing import Dict
import logging
from pkg.plugin.context import EventContext

class MessageHandler:
    def __init__(self, reminder_manager, time_parser):
        self.reminder_manager = reminder_manager
        self.time_parser = time_parser
        self.logger = logging.getLogger(__name__)

    async def handle_message(self, ctx: EventContext, is_group: bool):
        """处理消息"""
        msg = ctx.event.text_message.strip()
        sender_id = str(ctx.event.sender_id)
        
        # 查看提醒列表
        if msg in ["查看提醒", "提醒列表", "我的提醒"]:
            await self._handle_list_reminders(ctx, sender_id)
        
        # 删除提醒
        elif msg.startswith("删除提醒"):
            await self._handle_delete_reminder(ctx, msg, sender_id)
        
        # 暂停/恢复提醒
        elif msg.startswith("暂停提醒"):
            await self._handle_pause_reminder(ctx, msg, sender_id)
        elif msg.startswith("恢复提醒"):
            await self._handle_resume_reminder(ctx, msg, sender_id)
        
        # 帮助信息
        elif msg in ["提醒帮助", "定时提醒帮助"]:
            await self._handle_help(ctx)

    async def _handle_list_reminders(self, ctx: EventContext, sender_id: str):
        """处理查看提醒列表请求"""
        user_reminders = self.reminder_manager.get_user_reminders(sender_id)
        
        if not user_reminders:
            await ctx.reply("📝 您当前没有任何提醒")
            return
            
        response = "📋 您的提醒列表：\n\n"
        for rid, data in user_reminders.items():
            target_time = datetime.fromisoformat(data['target_time'])
            time_str = target_time.strftime("%Y-%m-%d %H:%M")
            status = "✅" if data.get('active', True) else "⏸️"
            response += f"{status} {time_str} - {data['content']}\n"
            
        await ctx.reply(response)

    async def _handle_delete_reminder(self, ctx: EventContext, msg: str, sender_id: str):
        """处理删除提醒请求"""
        try:
            # 提取提醒ID
            reminder_id = msg.replace("删除提醒", "").strip()
            if not reminder_id:
                await ctx.reply("❌ 请指定要删除的提醒ID")
                return
                
            # 获取提醒数据
            reminder_data = self.reminder_manager.get_reminder(reminder_id)
            if not reminder_data:
                await ctx.reply("❌ 未找到指定的提醒")
                return
                
            # 检查权限
            if reminder_data['sender_id'] != sender_id:
                await ctx.reply("❌ 您没有权限删除此提醒")
                return
                
            # 取消任务
            self.reminder_manager.cancel_task(reminder_id)
            
            # 删除提醒
            self.reminder_manager.remove_reminder(reminder_id)
            await self.reminder_manager.save_reminders()
            
            await ctx.reply(f"✅ 已删除提醒：{reminder_data['content']}")
            
        except Exception as e:
            self.logger.error(f"删除提醒失败: {e}")
            await ctx.reply("❌ 删除提醒失败，请重试")

    async def _handle_pause_reminder(self, ctx: EventContext, msg: str, sender_id: str):
        """处理暂停提醒请求"""
        await self._toggle_reminder(ctx, msg, sender_id, False)

    async def _handle_resume_reminder(self, ctx: EventContext, msg: str, sender_id: str):
        """处理恢复提醒请求"""
        await self._toggle_reminder(ctx, msg, sender_id, True)

    async def _toggle_reminder(self, ctx: EventContext, msg: str, sender_id: str, active: bool):
        """处理暂停/恢复提醒请求"""
        try:
            # 提取提醒ID
            reminder_id = msg.replace("暂停提醒", "").replace("恢复提醒", "").strip()
            if not reminder_id:
                await ctx.reply("❌ 请指定要操作的提醒ID")
                return
                
            # 获取提醒数据
            reminder_data = self.reminder_manager.get_reminder(reminder_id)
            if not reminder_data:
                await ctx.reply("❌ 未找到指定的提醒")
                return
                
            # 检查权限
            if reminder_data['sender_id'] != sender_id:
                await ctx.reply("❌ 您没有权限操作此提醒")
                return
                
            # 更新状态
            reminder_data['active'] = active
            self.reminder_manager.update_reminder(reminder_id, reminder_data)
            await self.reminder_manager.save_reminders()
            
            # 处理任务
            if active:
                # 恢复任务
                target_time = datetime.fromisoformat(reminder_data['target_time'])
                if target_time > datetime.now():
                    await self._schedule_reminder(reminder_id, reminder_data)
                await ctx.reply(f"✅ 已恢复提醒：{reminder_data['content']}")
            else:
                # 暂停任务
                self.reminder_manager.cancel_task(reminder_id)
                await ctx.reply(f"⏸️ 已暂停提醒：{reminder_data['content']}")
                
        except Exception as e:
            self.logger.error(f"操作提醒失败: {e}")
            await ctx.reply("❌ 操作失败，请重试")

    async def _handle_help(self, ctx: EventContext):
        """处理帮助信息请求"""
        help_text = """📝 提醒插件使用帮助：

1️⃣ 设置提醒
• 格式：提醒 [内容] [时间]
• 示例：
  - 提醒 开会 明天下午3点
  - 提醒 吃药 30分钟后
  - 提醒 买菜 每周六上午10点

2️⃣ 查看提醒
• 命令：查看提醒
• 功能：显示所有已设置的提醒

3️⃣ 管理提醒
• 删除提醒 [ID]：删除指定提醒
• 暂停提醒 [ID]：暂停指定提醒
• 恢复提醒 [ID]：恢复指定提醒

4️⃣ 时间格式支持
• 相对时间：30分钟后、2小时后、3天后
• 具体日期：明天下午3点、后天晚上8点
• 星期时间：本周六晚上9点、下周一上午10点
• 标准格式：2025-06-08 15:30

💡 提示：时间支持自然语言，可以灵活表达"""
        
        await ctx.reply(help_text) 