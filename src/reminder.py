import json
import os
import asyncio
from datetime import datetime
from typing import Dict, Optional
import logging

class ReminderManager:
    def __init__(self, data_file: str = "reminders.json"):
        self.reminders: Dict[str, Dict] = {}
        self.data_file = data_file
        self.running_tasks = {}
        self.logger = logging.getLogger(__name__)

    async def load_reminders(self):
        """从文件加载提醒数据"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.reminders = json.load(f)
                    # 转换旧格式的时间字符串为datetime对象
                    for reminder_data in self.reminders.values():
                        if isinstance(reminder_data.get('target_time'), str):
                            reminder_data['target_time'] = reminder_data['target_time']
        except Exception as e:
            self.logger.error(f"加载提醒数据失败: {e}")
            self.reminders = {}

    async def save_reminders(self):
        """保存提醒数据到文件"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"保存提醒数据失败: {e}")

    def get_reminder(self, reminder_id: str) -> Optional[Dict]:
        """获取指定ID的提醒"""
        return self.reminders.get(reminder_id)

    def add_reminder(self, reminder_id: str, reminder_data: Dict):
        """添加新提醒"""
        self.reminders[reminder_id] = reminder_data

    def remove_reminder(self, reminder_id: str):
        """删除提醒"""
        if reminder_id in self.reminders:
            del self.reminders[reminder_id]

    def update_reminder(self, reminder_id: str, reminder_data: Dict):
        """更新提醒数据"""
        if reminder_id in self.reminders:
            self.reminders[reminder_id].update(reminder_data)

    def get_user_reminders(self, user_id: str) -> Dict[str, Dict]:
        """获取用户的所有提醒"""
        return {rid: data for rid, data in self.reminders.items() 
                if data.get('sender_id') == user_id}

    def cancel_task(self, reminder_id: str):
        """取消提醒任务"""
        if reminder_id in self.running_tasks:
            self.running_tasks[reminder_id].cancel()
            del self.running_tasks[reminder_id]

    def add_task(self, reminder_id: str, task: asyncio.Task):
        """添加提醒任务"""
        self.running_tasks[reminder_id] = task 