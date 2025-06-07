import re
import calendar
import dateparser
from datetime import datetime, timedelta
import logging

class TimeParser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def parse_time_natural(self, time_str: str) -> datetime:
        """增强的自然语言时间解析"""
        try:
            self.logger.debug(f"开始解析时间: '{time_str}'")
            
            # 预处理时间字符串
            processed_time = await self._preprocess_time_string(time_str)
            self.logger.debug(f"预处理后: '{processed_time}'")
            
            # 尝试多种解析策略
            parsers = [
                self._parse_weekday_time,      # 星期相关
                self._parse_relative_days,      # 相对日期
                self._parse_specific_time,      # 具体时间
                self._parse_with_dateparser,    # dateparser库
                self._parse_time_manual         # 手动解析
            ]
            
            for parser in parsers:
                result = await parser(processed_time)
                if result and result > datetime.now():
                    self.logger.debug(f"解析成功 ({parser.__name__}): {result}")
                    return result
            
            # 如果所有方法都失败，尝试原始字符串
            for parser in parsers:
                result = await parser(time_str)
                if result and result > datetime.now():
                    self.logger.debug(f"原始字符串解析成功 ({parser.__name__}): {result}")
                    return result
                    
            return None
            
        except Exception as e:
            self.logger.error(f"解析时间失败: {e}")
            return None

    async def _preprocess_time_string(self, time_str: str) -> str:
        """预处理时间字符串"""
        # 移除多余的空格
        time_str = time_str.strip()
        
        # 统一时间单位
        time_str = time_str.replace("小时", "时").replace("分钟", "分")
        
        # 处理"今天"、"明天"等
        if "今天" in time_str:
            time_str = time_str.replace("今天", datetime.now().strftime("%Y-%m-%d"))
        elif "明天" in time_str:
            tomorrow = datetime.now() + timedelta(days=1)
            time_str = time_str.replace("明天", tomorrow.strftime("%Y-%m-%d"))
        elif "后天" in time_str:
            day_after = datetime.now() + timedelta(days=2)
            time_str = time_str.replace("后天", day_after.strftime("%Y-%m-%d"))
            
        return time_str

    async def _parse_weekday_time(self, time_str: str) -> datetime:
        """解析星期相关的时间"""
        weekday_map = {
            "周一": 0, "周二": 1, "周三": 2, "周四": 3, "周五": 4, "周六": 5, "周日": 6,
            "星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3, "星期五": 4, "星期六": 5, "星期日": 6,
            "礼拜一": 0, "礼拜二": 1, "礼拜三": 2, "礼拜四": 3, "礼拜五": 4, "礼拜六": 5, "礼拜日": 6
        }
        
        for weekday_name, weekday_num in weekday_map.items():
            if weekday_name in time_str:
                # 提取时间部分
                time_match = re.search(r'(\d{1,2})[:：]?(\d{1,2})?', time_str)
                if time_match:
                    hour = int(time_match.group(1))
                    minute = int(time_match.group(2)) if time_match.group(2) else 0
                    
                    # 获取下一个指定星期几的日期
                    target_date = self._get_next_weekday(weekday_num)
                    return self._combine_date_time(target_date, hour, f"{minute:02d}")
        return None

    async def _parse_relative_days(self, time_str: str) -> datetime:
        """解析相对日期"""
        now = datetime.now()
        
        # 处理"x天后"
        days_match = re.search(r'(\d+)天后', time_str)
        if days_match:
            days = int(days_match.group(1))
            target_date = now + timedelta(days=days)
            return self._combine_date_time(target_date, now.hour, f"{now.minute:02d}")
            
        # 处理"x小时后"
        hours_match = re.search(r'(\d+)小时后', time_str)
        if hours_match:
            hours = int(hours_match.group(1))
            return now + timedelta(hours=hours)
            
        # 处理"x分钟后"
        minutes_match = re.search(r'(\d+)分钟后', time_str)
        if minutes_match:
            minutes = int(minutes_match.group(1))
            return now + timedelta(minutes=minutes)
            
        return None

    async def _parse_specific_time(self, time_str: str) -> datetime:
        """解析具体时间"""
        # 尝试匹配"HH:MM"或"HH时MM分"格式
        time_match = re.search(r'(\d{1,2})[:：]?(\d{1,2})?', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            
            # 如果时间已经过去，设置为明天
            target_date = datetime.now()
            if hour < target_date.hour or (hour == target_date.hour and minute <= target_date.minute):
                target_date += timedelta(days=1)
                
            return self._combine_date_time(target_date, hour, f"{minute:02d}")
        return None

    async def _parse_with_dateparser(self, time_str: str) -> datetime:
        """使用dateparser库解析时间"""
        try:
            result = dateparser.parse(time_str)
            if result and result > datetime.now():
                return result
        except Exception as e:
            self.logger.debug(f"dateparser解析失败: {e}")
        return None

    async def _parse_time_manual(self, time_str: str) -> datetime:
        """手动解析时间"""
        now = datetime.now()
        
        # 处理"上午/下午/晚上"
        if "上午" in time_str:
            time_str = time_str.replace("上午", "")
            is_pm = False
        elif "下午" in time_str or "晚上" in time_str:
            time_str = time_str.replace("下午", "").replace("晚上", "")
            is_pm = True
        else:
            is_pm = None
            
        # 提取时间
        time_match = re.search(r'(\d{1,2})[:：]?(\d{1,2})?', time_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            
            # 处理12小时制
            if is_pm is not None:
                if is_pm and hour < 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0
                    
            # 如果时间已经过去，设置为明天
            target_date = now
            if hour < target_date.hour or (hour == target_date.hour and minute <= target_date.minute):
                target_date += timedelta(days=1)
                
            return self._combine_date_time(target_date, hour, f"{minute:02d}")
        return None

    def _get_next_weekday(self, weekday: int, weeks_ahead: int = 0) -> datetime:
        """获取下一个指定星期几的日期"""
        now = datetime.now()
        days_ahead = weekday - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        days_ahead += weeks_ahead * 7
        return now + timedelta(days=days_ahead)

    def _combine_date_time(self, date, hour: int, time_str: str) -> datetime:
        """组合日期和时间"""
        try:
            return datetime.combine(date.date(), datetime.strptime(f"{hour}:{time_str}", "%H:%M").time())
        except ValueError as e:
            self.logger.error(f"时间组合失败: {e}")
            return None 