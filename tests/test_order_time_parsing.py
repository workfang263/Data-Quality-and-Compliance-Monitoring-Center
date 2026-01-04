"""
订单时间解析测试脚本（Pytest）

测试目标：
1. 测试 _get_order_beijing_time() 函数的时间解析功能
2. 验证各种时间格式的解析正确性
3. 验证时区转换的正确性
4. 验证返回类型是无时区的datetime
5. 验证错误处理（缺失placed_at字段）

【测试开发工程师要点】
- 边界测试：测试各种时间格式的边界情况
- 类型测试：确保返回类型正确
- 错误处理测试：测试异常情况的处理
- 数据驱动测试：使用参数化测试覆盖多种场景
"""
import pytest
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytz

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_sync import _get_order_beijing_time


class TestOrderTimeParsing:
    """订单时间解析测试类"""
    
    def test_utc_time_with_z(self):
        """
        测试UTC时间（带Z）的解析和转换
        
        【测试要点】
        - 输入：2025-12-31T10:00:00Z（UTC时间）
        - 期望：2025-12-31 18:00:00（北京时间，UTC+8）
        - 验证：返回无时区的datetime对象
        """
        order = {
            'id': 'test_order_1',
            'placed_at': '2025-12-31T10:00:00Z'
        }
        
        result = _get_order_beijing_time(order)
        
        # 验证返回结果
        assert result is not None, "应该成功解析UTC时间（带Z）"
        assert isinstance(result, datetime), "应该返回datetime对象"
        assert result.tzinfo is None, "应该返回无时区的datetime对象"
        
        # 验证时间转换正确性（UTC 10:00 = 北京时间 18:00）
        expected = datetime(2025, 12, 31, 18, 0, 0)
        assert result == expected, f"UTC时间转换错误: 期望 {expected}, 实际 {result}"
    
    def test_utc_time_with_offset(self):
        """
        测试UTC时间（+00:00）的解析和转换
        
        【测试要点】
        - 输入：2025-12-31T10:00:00+00:00（UTC时间）
        - 期望：2025-12-31 18:00:00（北京时间，UTC+8）
        - 验证：返回无时区的datetime对象
        """
        order = {
            'id': 'test_order_2',
            'placed_at': '2025-12-31T10:00:00+00:00'
        }
        
        result = _get_order_beijing_time(order)
        
        # 验证返回结果
        assert result is not None, "应该成功解析UTC时间（+00:00）"
        assert isinstance(result, datetime), "应该返回datetime对象"
        assert result.tzinfo is None, "应该返回无时区的datetime对象"
        
        # 验证时间转换正确性
        expected = datetime(2025, 12, 31, 18, 0, 0)
        assert result == expected, f"UTC时间转换错误: 期望 {expected}, 实际 {result}"
    
    def test_beijing_time(self):
        """
        测试北京时间（+08:00）的解析
        
        【测试要点】
        - 输入：2025-12-31T18:00:00+08:00（已经是北京时间）
        - 期望：2025-12-31 18:00:00（直接使用，不转换）
        - 验证：返回无时区的datetime对象
        """
        order = {
            'id': 'test_order_3',
            'placed_at': '2025-12-31T18:00:00+08:00'
        }
        
        result = _get_order_beijing_time(order)
        
        # 验证返回结果
        assert result is not None, "应该成功解析北京时间（+08:00）"
        assert isinstance(result, datetime), "应该返回datetime对象"
        assert result.tzinfo is None, "应该返回无时区的datetime对象"
        
        # 验证时间正确性（已经是北京时间，不转换）
        expected = datetime(2025, 12, 31, 18, 0, 0)
        assert result == expected, f"北京时间解析错误: 期望 {expected}, 实际 {result}"
    
    def test_no_timezone(self):
        """
        测试无时区信息的解析
        
        【测试要点】
        - 输入：2025-12-31T18:00:00（无时区信息）
        - 期望：使用parse_iso8601解析，然后转换为北京时间
        - 验证：返回无时区的datetime对象
        """
        order = {
            'id': 'test_order_4',
            'placed_at': '2025-12-31T18:00:00'
        }
        
        result = _get_order_beijing_time(order)
        
        # 验证返回结果
        assert result is not None, "应该成功解析无时区信息的时间"
        assert isinstance(result, datetime), "应该返回datetime对象"
        assert result.tzinfo is None, "应该返回无时区的datetime对象"
    
    def test_missing_placed_at(self):
        """
        测试缺失placed_at字段的情况
        
        【测试要点】
        - 输入：订单对象没有placed_at字段
        - 期望：返回None（不抛出异常）
        - 验证：记录错误日志（⚠️ 因为这是数据异常，不是警告）
        - ⚠️ 重要：根据官方确认，placed_at字段一定存在，如果缺失说明数据异常
        """
        order = {
            'id': 'test_order_5',
            # 没有placed_at字段
        }
        
        # 使用patch捕获日志
        with patch('data_sync.logger') as mock_logger:
            result = _get_order_beijing_time(order)
            
            # 验证返回None
            assert result is None, "缺失placed_at字段时应该返回None"
            
            # ⚠️ 验证记录了错误日志（不是警告，因为这是数据异常）
            mock_logger.error.assert_called_once()
            error_msg = str(mock_logger.error.call_args)
            assert 'placed_at' in error_msg or '数据异常' in error_msg, "应该记录关于缺失placed_at的错误日志"
    
    def test_empty_placed_at(self):
        """
        测试placed_at字段为空字符串的情况
        
        【测试要点】
        - 输入：placed_at为空字符串
        - 期望：返回None（不抛出异常）
        - 验证：记录错误日志（⚠️ 因为这是数据异常，不是警告）
        """
        order = {
            'id': 'test_order_6',
            'placed_at': ''
        }
        
        with patch('data_sync.logger') as mock_logger:
            result = _get_order_beijing_time(order)
            
            # 验证返回None
            assert result is None, "placed_at为空字符串时应该返回None"
            
            # ⚠️ 验证记录了错误日志（不是警告，因为这是数据异常）
            mock_logger.error.assert_called_once()
            error_msg = str(mock_logger.error.call_args)
            assert 'placed_at' in error_msg or '数据异常' in error_msg, "应该记录关于缺失placed_at的错误日志"
    
    def test_invalid_time_format(self):
        """
        测试无效时间格式的解析
        
        【测试要点】
        - 输入：无效的时间格式字符串
        - 期望：返回None（不抛出异常）
        - 验证：记录警告日志
        """
        order = {
            'id': 'test_order_7',
            'placed_at': 'invalid_time_format'
        }
        
        with patch('data_sync.logger') as mock_logger:
            result = _get_order_beijing_time(order)
            
            # 验证返回None
            assert result is None, "无效时间格式时应该返回None"
            
            # 验证记录了警告日志
            mock_logger.warning.assert_called_once()
    
    def test_return_type_naive(self):
        """
        测试返回类型是无时区的datetime
        
        【测试要点】
        - 验证所有成功解析的情况都返回无时区的datetime
        - 这是关键测试，避免混合类型比较错误
        """
        test_cases = [
            {'placed_at': '2025-12-31T10:00:00Z'},  # UTC时间（带Z）
            {'placed_at': '2025-12-31T10:00:00+00:00'},  # UTC时间（+00:00）
            {'placed_at': '2025-12-31T18:00:00+08:00'},  # 北京时间（+08:00）
        ]
        
        for order in test_cases:
            order['id'] = 'test_order'
            result = _get_order_beijing_time(order)
            
            assert result is not None, f"应该成功解析: {order['placed_at']}"
            assert isinstance(result, datetime), f"应该返回datetime对象: {order['placed_at']}"
            assert result.tzinfo is None, f"应该返回无时区的datetime对象: {order['placed_at']}"
    
    def test_timezone_conversion_accuracy(self):
        """
        测试时区转换的准确性
        
        【测试要点】
        - 测试多个UTC时间点的转换
        - 验证转换后的时间是否正确（UTC+8）
        """
        test_cases = [
            # (UTC时间, 期望的北京时间)
            ('2025-12-31T00:00:00Z', datetime(2025, 12, 31, 8, 0, 0)),   # UTC 00:00 = 北京时间 08:00
            ('2025-12-31T12:00:00Z', datetime(2025, 12, 31, 20, 0, 0)),  # UTC 12:00 = 北京时间 20:00
            ('2025-12-31T16:00:00Z', datetime(2026, 1, 1, 0, 0, 0)),      # UTC 16:00 = 北京时间 次日00:00
        ]
        
        for utc_time_str, expected_beijing_time in test_cases:
            order = {
                'id': 'test_order',
                'placed_at': utc_time_str
            }
            
            result = _get_order_beijing_time(order)
            
            assert result is not None, f"应该成功解析: {utc_time_str}"
            assert result == expected_beijing_time, (
                f"时区转换错误: UTC {utc_time_str} 应该转换为 {expected_beijing_time}, "
                f"实际得到 {result}"
            )
    
    @pytest.mark.parametrize("placed_at,expected_hour", [
        ('2025-12-31T10:00:00Z', 18),  # UTC 10:00 = 北京时间 18:00
        ('2025-12-31T14:00:00Z', 22),  # UTC 14:00 = 北京时间 22:00
        ('2025-12-31T18:00:00+08:00', 18),  # 已经是北京时间 18:00
    ])
    def test_time_parsing_parametrized(self, placed_at, expected_hour):
        """
        参数化测试：测试多种时间格式的解析
        
        【测试要点】
        - 使用pytest的参数化功能，覆盖多种场景
        - 验证解析后的小时数是否正确
        """
        order = {
            'id': 'test_order',
            'placed_at': placed_at
        }
        
        result = _get_order_beijing_time(order)
        
        assert result is not None, f"应该成功解析: {placed_at}"
        assert result.hour == expected_hour, (
            f"解析后的小时数错误: 期望 {expected_hour}, 实际 {result.hour}, "
            f"输入: {placed_at}"
        )


if __name__ == '__main__':
    # 直接运行测试
    pytest.main([__file__, '-v', '-s'])

