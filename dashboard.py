"""
Streamlit 前端看板
"""
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
import json
import logging
from pathlib import Path
from streamlit.components.v1 import html

from database import Database
from utils import beijing_time, hash_password, verify_password, setup_logging
from config import STREAMLIT_CONFIG, LOG_CONFIG
from check_port import is_port_in_use, find_available_port

# 尝试导入PyEcharts
try:
    from pyecharts import options as opts
    from pyecharts.charts import Line
    from pyecharts.commons.utils import JsCode
    from streamlit_echarts import st_pyecharts
    use_pyecharts = True
except ImportError:
    use_pyecharts = False
    JsCode = None
    st_pyecharts = None

# 配置日志
setup_logging(LOG_CONFIG['log_file'], LOG_CONFIG['log_level'])
logger = logging.getLogger(__name__)

# 页面配置
st.set_page_config(
    page_title="Shoplazza 多店铺数据看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化数据库
db = Database()


def save_login_token(username: str, remember_me: bool = False):
    """保存登录令牌到文件（每个用户独立的文件）"""
    if not remember_me:
        return
    
    # 使用用户名作为文件名，支持多用户
    token_file = Path(f"logs/.login_token_{username}")
    token_file.parent.mkdir(exist_ok=True)
    
    token_data = {
        'username': username,
        'login_time': datetime.now().isoformat(),
        'expire_time': (datetime.now() + timedelta(days=7)).isoformat()
    }
    
    try:
        with open(token_file, 'w', encoding='utf-8') as f:
            json.dump(token_data, f)
    except Exception as e:
        logger.warning(f"保存登录令牌失败: {e}")


def load_login_token(username: Optional[str] = None) -> Optional[Dict]:
    """从文件加载登录令牌（支持多用户）"""
    # 如果提供了用户名，直接加载对应的令牌文件
    if username:
        token_file = Path(f"logs/.login_token_{username}")
        if token_file.exists():
            try:
                with open(token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                
                # 检查是否过期
                expire_time = datetime.fromisoformat(token_data['expire_time'])
                if datetime.now() > expire_time:
                    token_file.unlink()  # 删除过期文件
                    return None
                
                return token_data
            except Exception as e:
                logger.warning(f"加载登录令牌失败: {e}")
                return None
    
    # 如果没有提供用户名，尝试从所有令牌文件中找到一个未过期的
    # （这种情况通常发生在页面首次加载时）
    logs_dir = Path("logs")
    if not logs_dir.exists():
        return None
    
    try:
        token_files = list(logs_dir.glob(".login_token_*"))
        for token_file in token_files:
            try:
                with open(token_file, 'r', encoding='utf-8') as f:
                    token_data = json.load(f)
                
                # 检查是否过期
                expire_time = datetime.fromisoformat(token_data['expire_time'])
                if datetime.now() > expire_time:
                    token_file.unlink()  # 删除过期文件
                    continue
                
                return token_data
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"扫描登录令牌失败: {e}")
    
    return None


def clear_login_token(username: Optional[str] = None):
    """清除登录令牌（支持多用户）"""
    if username:
        # 清除指定用户的令牌
        token_file = Path(f"logs/.login_token_{username}")
        if token_file.exists():
            try:
                token_file.unlink()
            except Exception as e:
                logger.warning(f"清除登录令牌失败: {e}")
    else:
        # 如果没有提供用户名，尝试清除当前session中的用户名对应的令牌
        if 'username' in st.session_state and st.session_state.username:
            token_file = Path(f"logs/.login_token_{st.session_state.username}")
            if token_file.exists():
                try:
                    token_file.unlink()
                except Exception as e:
                    logger.warning(f"清除登录令牌失败: {e}")


def check_login():
    """检查登录状态（支持多用户）"""
    # 首先检查 session_state
    if 'logged_in' in st.session_state and st.session_state.logged_in:
        # 如果已经有登录状态，验证令牌是否仍然有效
        if st.session_state.username:
            token_data = load_login_token(st.session_state.username)
            if token_data:
                return True
            else:
                # 令牌已过期或不存在，清除登录状态
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.role = None
                return False
        return True
    
    # 如果 session_state 中没有，尝试从文件加载
    # 注意：这里不指定用户名，会尝试加载所有令牌文件中的第一个有效令牌
    # 这在多用户场景下可能有问题，但可以作为首次加载的尝试
    token_data = load_login_token()
    if token_data:
        st.session_state.logged_in = True
        st.session_state.username = token_data['username']
        # 从数据库获取用户角色
        user = db.get_user_by_username(token_data['username'])
        if user:
            st.session_state.role = user['role']
        else:
            # 如果用户不存在，清除令牌
            clear_login_token(token_data['username'])
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.role = None
            return False
        return True
    
    # 都没有，返回 False
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
    
    return False


def login_page():
    """登录页面"""
    st.title("🔐 登录")
    
    with st.form("login_form"):
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")
        remember_me = st.checkbox("记住我（7天内免登录）", value=False)
        submit = st.form_submit_button("登录")
        
        if submit:
            user = db.get_user_by_username(username)
            if user and verify_password(password, user['password_hash']):
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = user['role']
                
                # 如果勾选了"记住我"，保存令牌
                if remember_me:
                    save_login_token(username, remember_me=True)
                
                st.success("登录成功！")
                st.rerun()
            else:
                st.error("用户名或密码错误")


def format_number(num: float) -> str:
    """格式化数字显示"""
    if num >= 10000:
        return f"{num/10000:.2f}万"
    elif num >= 1000:
        return f"{num/1000:.1f}千"
    else:
        return f"{num:.0f}"


def create_chart_data(data: List[Dict], granularity: str) -> pd.DataFrame:
    """创建图表数据"""
    if not data:
        return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    if granularity == 'hour':
        df['time'] = pd.to_datetime(df['time_hour'])
    else:  # day
        df['time'] = pd.to_datetime(df['date'])
    
    return df


def init_session_state():
    """初始化所有session_state变量，只在第一次访问时设置默认值"""
    today = beijing_time().date()
    
    # 日期范围（默认今天）
    if 'start_date' not in st.session_state:
        st.session_state.start_date = today
    if 'end_date' not in st.session_state:
        st.session_state.end_date = today
    
    # 颗粒度（默认小时）
    if 'granularity' not in st.session_state:
        st.session_state.granularity = 'hour'
    
    # 时段选择（默认全天）
    if 'time_range' not in st.session_state:
        st.session_state.time_range = '全天'
    if 'start_hour' not in st.session_state:
        st.session_state.start_hour = None
    if 'end_hour' not in st.session_state:
        st.session_state.end_hour = None
    
    # 对比模式
    if 'enable_compare' not in st.session_state:
        st.session_state.enable_compare = False
    if 'compare_ranges' not in st.session_state:
        st.session_state.compare_ranges = []
    
    # 指标显示开关
    if 'show_gmv' not in st.session_state:
        st.session_state.show_gmv = True
    if 'show_orders' not in st.session_state:
        st.session_state.show_orders = True
    if 'show_visitors' not in st.session_state:
        st.session_state.show_visitors = False  # 默认不显示
    if 'show_aov' not in st.session_state:
        st.session_state.show_aov = False  # 默认不显示
    if 'show_spend' not in st.session_state:
        st.session_state.show_spend = False  # 默认不显示
    if 'show_roas' not in st.session_state:
        st.session_state.show_roas = False  # 默认不显示
    
    # 店铺选择（默认选择"总店铺"）
    if 'selected_store' not in st.session_state:
        st.session_state.selected_store = 'ALL_STORES'
    if 'selected_store_name' not in st.session_state:
        st.session_state.selected_store_name = '总店铺'
    
    # 店铺列表区域的日期选择
    if 'store_list_date_start' not in st.session_state:
        st.session_state.store_list_date_start = today  # 默认今天
    if 'store_list_date_end' not in st.session_state:
        st.session_state.store_list_date_end = today  # 默认今天
    if 'store_list_sort_by' not in st.session_state:
        st.session_state.store_list_sort_by = 'store_name'  # 默认按店铺名称排序（与侧边栏一致）
    if 'store_list_sort_order' not in st.session_state:
        st.session_state.store_list_sort_order = 'asc'  # 默认升序

    # 负责人弹窗状态（仅用 owner_sel + 指标开关）
    if 'owner_sel' not in st.session_state:
        st.session_state.owner_sel = None
    if 'owner_metric_show_gmv' not in st.session_state:
        st.session_state.owner_metric_show_gmv = True
    if 'owner_metric_show_orders' not in st.session_state:
        st.session_state.owner_metric_show_orders = False
    if 'owner_metric_show_spend' not in st.session_state:
        st.session_state.owner_metric_show_spend = True
    if 'owner_metric_show_aov' not in st.session_state:
        st.session_state.owner_metric_show_aov = False
    if 'owner_metric_show_roas' not in st.session_state:
        st.session_state.owner_metric_show_roas = True


def render_dashboard():
    """主看板页面"""
    # 初始化所有session_state变量
    init_session_state()
    
    # 侧边栏筛选
    with st.sidebar:
        # 店铺选择（固定为"总店铺"）
        st.header("🏪 店铺选择")
        st.info("📊 **总店铺** - 查看所有店铺的汇总数据")
        
        # 固定设置为"总店铺"
        st.session_state.selected_store = 'ALL_STORES'
        st.session_state.selected_store_name = '总店铺'
        
        st.divider()  # 分隔线
        
        st.header("📅 时间筛选")
        st.caption("💡 选择要查看的日期范围和时间段")
        
        # 日期选择（使用key参数绑定到session_state，key名称与变量名一致）
        col1, col2 = st.columns(2)
        with col1:
            # 不使用key参数，手动同步到session_state，这样快捷按钮可以更新值
            start_date = st.date_input(
                "开始日期", 
                value=st.session_state.start_date, 
                help="选择查询的开始日期"
            )
            st.session_state.start_date = start_date
        with col2:
            # 不使用key参数，手动同步到session_state，这样快捷按钮可以更新值
            end_date = st.date_input(
                "结束日期", 
                value=st.session_state.end_date, 
                help="选择查询的结束日期"
            )
            st.session_state.end_date = end_date
        
        # 快捷日期按钮（只更新日期范围，保留用户的其他选择如颗粒度、时段等）
        st.subheader("⚡ 快捷选择")
        st.caption("💡 快速选择常用的时间范围（保留您选择的颗粒度和时段）")
        quick_buttons = st.columns(5)  # 改为5列，添加"今天"按钮
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        with quick_buttons[0]:
            if st.button("今天", key="btn_today"):
                st.session_state.start_date = today
                st.session_state.end_date = today
                # 不修改颗粒度和其他设置，保留用户选择
                st.rerun()
        with quick_buttons[1]:
            if st.button("昨天", key="btn_yesterday"):
                st.session_state.start_date = yesterday
                st.session_state.end_date = yesterday
                # 不修改颗粒度和其他设置，保留用户选择
                st.rerun()
        with quick_buttons[2]:
            if st.button("最近7天", key="btn_7days"):
                st.session_state.start_date = yesterday - timedelta(days=6)
                st.session_state.end_date = yesterday
                # 不修改颗粒度和其他设置，保留用户选择
                st.rerun()
        with quick_buttons[3]:
            if st.button("最近30天", key="btn_30days"):
                st.session_state.start_date = yesterday - timedelta(days=29)
                st.session_state.end_date = yesterday
                # 不修改颗粒度和其他设置，保留用户选择
                st.rerun()
        with quick_buttons[4]:
            if st.button("最近3个月", key="btn_90days"):
                st.session_state.start_date = yesterday - timedelta(days=89)
                st.session_state.end_date = yesterday
                # 不修改颗粒度和其他设置，保留用户选择
                st.rerun()
        
        # 日内时段选择（绑定到session_state）
        st.subheader("⏰ 日内时段")
        st.caption("💡 筛选一天中的特定时间段，如：早上8:00-12:00 或 晚上18:00-24:00")
        time_range_options = ["全天", "上午 (00:00-12:00)", "下午 (12:00-18:00)", "晚上 (18:00-24:00)", "自定义"]
        current_time_range_index = time_range_options.index(st.session_state.time_range) if st.session_state.time_range in time_range_options else 0
        
        st.session_state.time_range = st.selectbox(
            "选择时段",
            time_range_options,
            index=current_time_range_index,
            key="time_range_selectbox",
            help="选择要查看的时间段：\n- 全天：查看0:00-24:00的所有数据\n- 上午：查看0:00-12:00的数据\n- 下午：查看12:00-18:00的数据\n- 晚上：查看18:00-24:00的数据\n- 自定义：手动选择时间段"
        )
        
        start_hour = None
        end_hour = None
        
        if st.session_state.time_range == "上午 (00:00-12:00)":
            start_hour, end_hour = 0, 12
        elif st.session_state.time_range == "下午 (12:00-18:00)":
            start_hour, end_hour = 12, 18
        elif st.session_state.time_range == "晚上 (18:00-24:00)":
            start_hour, end_hour = 18, 24
        elif st.session_state.time_range == "自定义":
            col1, col2 = st.columns(2)
            with col1:
                # 确保初始值不超过 23（避免从"晚上"切换过来时，end_hour=24导致报错）
                start_hour_default = st.session_state.start_hour if st.session_state.start_hour is not None else 0
                if start_hour_default > 23:
                    start_hour_default = 23
                
                start_hour = st.number_input(
                    "开始时间（小时）", 
                    0, 23, 
                    start_hour_default,
                    key="start_hour_input"
                )
            with col2:
                # 确保初始值不超过 23（如果之前是24，转换为23）
                end_hour_default = st.session_state.end_hour if st.session_state.end_hour is not None else 23
                if end_hour_default > 23:
                    end_hour_default = 23
                
                end_hour = st.number_input(
                    "结束时间（小时）", 
                    0, 23, 
                    end_hour_default,
                    key="end_hour_input"
                )
            st.session_state.start_hour = start_hour
            st.session_state.end_hour = end_hour
        
        # 更新session_state中的时段值
        if start_hour is not None and end_hour is not None:
            st.session_state.start_hour = start_hour
            st.session_state.end_hour = end_hour
        else:
            st.session_state.start_hour = None
            st.session_state.end_hour = None
        
        # 颗粒度选择（绑定到session_state）
        st.subheader("📅 数据颗粒度")
        st.caption("💡 选择查看数据的时间粒度：按小时查看详细趋势，或按天查看汇总数据")
        granularity_index = 0 if st.session_state.granularity == 'hour' else 1
        granularity_choice = st.radio(
            "选择颗粒度", 
            ["小时", "天"], 
            horizontal=True,
            index=granularity_index,
            key="granularity_radio",
            help="小时模式：显示每个小时的数据点，适合分析一天内的详细趋势\n天模式：显示每天的数据汇总，适合分析长期趋势"
        )
        st.session_state.granularity = 'hour' if granularity_choice == '小时' else 'day'
        granularity = st.session_state.granularity
        
        # 对比功能
        st.subheader("对比模式")
        
        # 基础对比快捷按钮
        st.caption("💡 快速选择常用的对比组合，或使用下方的自由对比")
        quick_compare_cols = st.columns(3)
        quick_compare_type = None
        
        yesterday = (datetime.now() - timedelta(days=1)).date()
        today = yesterday  # 今天的数据还未统计，所以"今天"实际上是指昨天
        
        with quick_compare_cols[0]:
            if st.button("昨天 vs 前天", key="btn_yesterday_vs_daybefore", use_container_width=True, 
                        help="对比昨天和前天的数据"):
                quick_compare_type = "yesterday_vs_daybefore"
        with quick_compare_cols[1]:
            if st.button("上周 vs 本周", key="btn_lastweek_vs_thisweek", use_container_width=True,
                        help="对比上周和本周的数据（本周统计到昨天）"):
                quick_compare_type = "lastweek_vs_thisweek"
        with quick_compare_cols[2]:
            if st.button("上月 vs 本月", key="btn_lastmonth_vs_thismonth", use_container_width=True,
                        help="对比上月和本月的数据（本月统计到昨天）"):
                quick_compare_type = "lastmonth_vs_thismonth"
        
        # 处理快捷对比按钮（只更新日期和对比范围，保留用户选择的颗粒度和时段等设置）
        if quick_compare_type:
            enable_compare = True
            st.session_state.enable_compare = True
            
            if quick_compare_type == "yesterday_vs_daybefore":
                # 昨天 vs 前天
                day_before_yesterday = yesterday - timedelta(days=1)
                # 主时间段：昨天
                st.session_state.start_date = yesterday
                st.session_state.end_date = yesterday
                # 对比段：前天
                st.session_state.quick_compare_range = [{
                    'start': day_before_yesterday,
                    'end': day_before_yesterday,
                    'time_range': '全天',
                    'start_hour': None,
                    'end_hour': None
                }]
            
            elif quick_compare_type == "lastweek_vs_thisweek":
                # 上周 vs 本周
                # 获取本周一和上周一
                today_weekday = yesterday.weekday()  # 0=Monday, 6=Sunday
                this_week_monday = yesterday - timedelta(days=today_weekday)
                last_week_monday = this_week_monday - timedelta(days=7)
                last_week_sunday = this_week_monday - timedelta(days=1)
                
                # 主时间段：本周（周一到昨天）
                st.session_state.start_date = this_week_monday
                st.session_state.end_date = yesterday
                # 对比段：上周（周一到周日）
                st.session_state.quick_compare_range = [{
                    'start': last_week_monday,
                    'end': last_week_sunday,
                    'time_range': '全天',
                    'start_hour': None,
                    'end_hour': None
                }]
            
            elif quick_compare_type == "lastmonth_vs_thismonth":
                # 上月 vs 本月
                # 获取本月1号和上月1号
                this_month_first = yesterday.replace(day=1)
                if yesterday.month == 1:
                    last_month_first = yesterday.replace(year=yesterday.year-1, month=12, day=1)
                    last_month_last = this_month_first - timedelta(days=1)
                else:
                    last_month_first = yesterday.replace(month=yesterday.month-1, day=1)
                    last_month_last = this_month_first - timedelta(days=1)
                
                # 主时间段：本月（1号到昨天）
                st.session_state.start_date = this_month_first
                st.session_state.end_date = yesterday
                # 对比段：上月（1号到最后一天）
                st.session_state.quick_compare_range = [{
                    'start': last_month_first,
                    'end': last_month_last,
                    'time_range': '全天',
                    'start_hour': None,
                    'end_hour': None
                }]
            
            st.rerun()
        
        # 检查是否有快捷对比设置
        if 'quick_compare_range' in st.session_state and st.session_state.quick_compare_range:
            enable_compare = True
        else:
            enable_compare = st.checkbox("启用对比", value=('enable_compare' in st.session_state and st.session_state.enable_compare))
            st.session_state.enable_compare = enable_compare
        
        compare_ranges = []
        if enable_compare:
            # 如果有快捷对比设置，先添加它
            if 'quick_compare_range' in st.session_state and st.session_state.quick_compare_range:
                compare_ranges.extend(st.session_state.quick_compare_range)
                # 显示快捷对比信息
                quick_info = []
                current_yesterday = (datetime.now() - timedelta(days=1)).date()
                for qr in st.session_state.quick_compare_range:
                    qr_days = (qr['end'] - qr['start']).days
                    if qr_days == 0:
                        # 单天对比
                        day_before_yesterday = current_yesterday - timedelta(days=1)
                        if qr['start'] == day_before_yesterday:
                            quick_info.append("前天（对比昨天）")
                        elif qr['start'] == current_yesterday:
                            quick_info.append("昨天（对比今天）")
                        else:
                            quick_info.append(qr['start'].strftime('%Y-%m-%d'))
                    elif qr_days == 6:
                        quick_info.append("上周（对比本周）")
                    elif qr_days >= 27:
                        quick_info.append("上月（对比本月）")
                    else:
                        quick_info.append(f"{qr['start'].strftime('%Y-%m-%d')} 至 {qr['end'].strftime('%Y-%m-%d')}")
                if quick_info:
                    st.info(f"📌 已启用快捷对比：{', '.join(quick_info)}")
                if st.button("清除快捷对比", key="clear_quick_compare"):
                    del st.session_state.quick_compare_range
                    st.session_state.enable_compare = False
                    st.rerun()
            
            # 自由对比（可以与快捷对比同时使用）
            max_free_compare = 4 - len(compare_ranges)  # 最多4个对比段
            if max_free_compare > 0:
                num_compare = st.number_input("对比段数（自由对比）", 0, max_free_compare, 0)
            else:
                num_compare = 0
                st.caption("💡 已达到最大对比段数（4个），如需添加更多，请先清除快捷对比")
            for i in range(num_compare):
                with st.expander(f"对比段 {i+1}", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        compare_start = st.date_input(f"开始日期 {i+1}", key=f"compare_start_{i}")
                    with col2:
                        compare_end = st.date_input(f"结束日期 {i+1}", key=f"compare_end_{i}")
                    compare_time_range = st.selectbox(
                        f"时段 {i+1}",
                        ["全天", "上午 (00:00-12:00)", "下午 (12:00-18:00)", "晚上 (18:00-24:00)", "自定义"],
                        key=f"compare_time_{i}",
                        help="选择对比段的时间段筛选"
                    )
                    
                    # 解析时段
                    compare_start_hour = None
                    compare_end_hour = None
                    if compare_time_range == "上午 (00:00-12:00)":
                        compare_start_hour, compare_end_hour = 0, 12
                    elif compare_time_range == "下午 (12:00-18:00)":
                        compare_start_hour, compare_end_hour = 12, 18
                    elif compare_time_range == "晚上 (18:00-24:00)":
                        compare_start_hour, compare_end_hour = 18, 24
                    elif compare_time_range == "自定义":
                        col3, col4 = st.columns(2)
                        with col3:
                            # 对比时间段的开始时间，默认0，确保不超过23
                            compare_start_hour_default = 0
                            compare_start_hour = st.number_input(
                                f"开始时间（小时）{i+1}", 
                                0, 23, 
                                compare_start_hour_default, 
                                key=f"compare_start_hour_{i}"
                            )
                        with col4:
                            # 对比时间段的结束时间，默认23，确保不超过23
                            compare_end_hour_default = 23
                            compare_end_hour = st.number_input(
                                f"结束时间（小时）{i+1}", 
                                0, 23, 
                                compare_end_hour_default, 
                                key=f"compare_end_hour_{i}"
                            )
                    
                    compare_ranges.append({
                        'start': compare_start,
                        'end': compare_end,
                        'time_range': compare_time_range,
                        'start_hour': compare_start_hour,
                        'end_hour': compare_end_hour
                    })
        
        # 指标选择
        st.subheader("📊 显示指标")
        st.caption("💡 勾选要在折线图中显示的指标，可以同时显示多个指标进行对比")
        store_display_text = '所有店铺' if st.session_state.selected_store == 'ALL_STORES' else st.session_state.selected_store_name
        show_gmv = st.checkbox(
            "总销售额 (total_gmv)", 
            value=st.session_state.get('show_gmv', True),
            key='show_gmv',
            help=f"{store_display_text}的销售总额"
        )
        show_orders = st.checkbox(
            "总订单数 (total_orders)", 
            value=st.session_state.get('show_orders', True),
            key='show_orders',
            help=f"{store_display_text}的订单总数"
        )
        show_visitors = st.checkbox(
            "总访客数 (total_visitors)", 
            value=st.session_state.get('show_visitors', False),  # 默认不显示
            key='show_visitors',
            help=f"{store_display_text}的独立访客数"
        )
        show_aov = st.checkbox(
            "平均客单价 (avg_order_value)", 
            value=st.session_state.get('show_aov', False),  # 默认不显示
            key='show_aov',
            help="平均每个订单的金额"
        )
        show_spend = st.checkbox(
            "广告花费 (total_spend)",
            value=st.session_state.get('show_spend', False),
            key='show_spend',
            help=f"{store_display_text}的广告花费汇总"
        )
        show_roas = st.checkbox(
            "ROAS (total_gmv / total_spend)",
            value=st.session_state.get('show_roas', False),
            key='show_roas',
            help="当花费为0时显示 N/A"
        )
        
        # 创建别名，使用session_state的值（确保状态持久化）
        show_gmv = st.session_state.show_gmv
        show_orders = st.session_state.show_orders
        show_visitors = st.session_state.show_visitors
        show_aov = st.session_state.show_aov
        show_spend = st.session_state.show_spend
        show_roas = st.session_state.show_roas
    
    # 主内容区
    st.markdown("---")
    
    start_datetime = datetime.combine(st.session_state.start_date, datetime.min.time())
    end_datetime = datetime.combine(st.session_state.end_date, datetime.max.time())
    
    # 获取主时间段数据（根据选择的店铺查询对应表的数据）
    if st.session_state.selected_store == 'ALL_STORES':
        # 查询汇总数据（总店铺）
        if granularity == 'hour':
            data = db.get_hourly_data_with_spend(start_datetime, end_datetime, start_hour, end_hour)
        else:
            data = db.get_daily_data_with_spend(start_datetime, end_datetime)
    else:
        # 查询单店铺数据
        if granularity == 'hour':
            data = db.get_store_hourly_data(
                st.session_state.selected_store, 
                start_datetime, end_datetime, 
                start_hour, end_hour
            )
        else:
            data = db.get_store_daily_data(
                st.session_state.selected_store,
                start_datetime, end_datetime,
                start_hour, end_hour
            )
    
    if not data:
        st.warning("该时间段内没有数据")
        return
    
    # 转换为DataFrame
    df = pd.DataFrame(data)
    
    # 获取对比段数据
    compare_data_list = []
    if enable_compare and compare_ranges:
        for i, compare_range in enumerate(compare_ranges):
            compare_start_dt = datetime.combine(compare_range['start'], datetime.min.time())
            compare_end_dt = datetime.combine(compare_range['end'], datetime.max.time())
            
            # 根据选择的店铺查询对比数据
            if st.session_state.selected_store == 'ALL_STORES':
                # 查询汇总数据（总店铺）
                if granularity == 'hour':
                    compare_data = db.get_hourly_data(
                        compare_start_dt, compare_end_dt, 
                        compare_range['start_hour'], compare_range['end_hour']
                    )
                else:
                    compare_data = db.get_daily_data(
                        compare_start_dt, compare_end_dt,
                        compare_range['start_hour'], compare_range['end_hour']
                    )
            else:
                # 查询单店铺数据
                if granularity == 'hour':
                    compare_data = db.get_store_hourly_data(
                        st.session_state.selected_store,
                        compare_start_dt, compare_end_dt, 
                        compare_range['start_hour'], compare_range['end_hour']
                    )
                else:
                    compare_data = db.get_store_daily_data(
                        st.session_state.selected_store,
                        compare_start_dt, compare_end_dt,
                        compare_range['start_hour'], compare_range['end_hour']
                    )
            
            if compare_data:
                compare_df = pd.DataFrame(compare_data)
                if granularity == 'hour':
                    compare_df['time'] = pd.to_datetime(compare_df['time_hour'])
                    # 修复访客数：确保同一天所有小时的访客数都相同
                    compare_df['date'] = compare_df['time'].dt.date
                    compare_df['total_visitors'] = compare_df.groupby('date')['total_visitors'].transform('max')
                    # 确保数据按时间排序
                    compare_df = compare_df.sort_values('time').reset_index(drop=True)
                else:
                    compare_df['time'] = pd.to_datetime(compare_df['date'])
                    # 天模式下：重新计算平均客单价（总销售额 / 总订单数）
                    compare_df['avg_order_value'] = compare_df.apply(
                        lambda row: float(row['total_gmv']) / int(row['total_orders']) 
                        if int(row['total_orders']) > 0 else 0.0,
                        axis=1
                    )
                    # 确保数据按时间排序
                    compare_df = compare_df.sort_values('time').reset_index(drop=True)
                compare_data_list.append(compare_df)
            else:
                st.warning(f"对比段 {i+1} ({compare_range['start']} 至 {compare_range['end']}) 没有数据")
    if granularity == 'hour':
        df['time'] = pd.to_datetime(df['time_hour'])
        # 修复访客数：确保同一天所有小时的访客数都相同（按天取最大值）
        # 因为访客数是按天去重的，不应该每个小时不同
        df['date'] = df['time'].dt.date
        df['total_visitors'] = df.groupby('date')['total_visitors'].transform('max')
        # 确保数据按时间排序（虽然数据库已排序，但groupby后可能顺序改变）
        df = df.sort_values('time').reset_index(drop=True)
    else:
        df['time'] = pd.to_datetime(df['date'])
        # 天模式下：重新计算平均客单价（总销售额 / 总订单数）
        # 因为数据库返回的avg_order_value是0，需要在dashboard中重新计算
        df['avg_order_value'] = df.apply(
            lambda row: float(row['total_gmv']) / int(row['total_orders']) 
            if int(row['total_orders']) > 0 else 0.0,
            axis=1
        )
        # 确保数据按时间排序（虽然数据库已排序，但确保一致性）
        df = df.sort_values('time').reset_index(drop=True)

    # 统一补充花费与 ROAS 列
    if 'total_spend' not in df.columns:
        df['total_spend'] = 0.0
    df['roas'] = df.apply(
        lambda row: float(row['total_gmv']) / float(row['total_spend'])
        if float(row['total_spend']) > 0 else np.nan,
        axis=1
    )
    
    # 指标卡片
    if st.session_state.selected_store == 'ALL_STORES':
        st.subheader("📊 核心指标汇总（所有店铺数据聚合）")
    else:
        st.subheader(f"📊 核心指标汇总（{st.session_state.selected_store_name}）")
    
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    
    with col1:
        total_gmv = df['total_gmv'].sum()
        # 直接显示完整数值，使用千分位格式化
        gmv_formatted = f"${total_gmv:,.2f}"
        st.metric(
            "总销售额 (GMV)", 
            f"{gmv_formatted}",
            help=f"{'所有店铺' if st.session_state.selected_store == 'ALL_STORES' else st.session_state.selected_store_name}在该时间段内的销售总额（USD，已过滤爬虫流量，仅包含已支付订单）"
        )
    
    with col2:
        total_orders = df['total_orders'].sum()
        st.metric(
            "总订单数", 
            f"{int(total_orders):,}",
            help=f"{'所有店铺' if st.session_state.selected_store == 'ALL_STORES' else st.session_state.selected_store_name}在该时间段内的订单总数（仅包含已支付订单）"
        )
    
    with col3:
        # 访客数是按天去重的，不应该累加所有小时
        # 应该按天取最大值（因为同一天所有小时的访客数应该相同），然后累加多天
        if granularity == 'hour':
            # 按小时查看时，按天分组取最大值（去重），然后累加
            total_visitors = df.groupby(df['time'].dt.date)['total_visitors'].max().sum()
        else:
            # 按天查看时，直接累加（每天的数据已经是去重后的）
            total_visitors = df['total_visitors'].sum()
        st.metric(
            "总访客数 (UV)", 
            f"{int(total_visitors):,}",
            help=f"{'所有店铺' if st.session_state.selected_store == 'ALL_STORES' else st.session_state.selected_store_name}在该时间段内的独立访客数（不过滤爬虫流量，包含所有访问，按天去重）"
        )
    
    with col4:
        # 平均客单价应该是：总销售额 ÷ 总订单数
        # 而不是对每小时的客单价求平均值（因为订单数可能不同，权重不同）
        total_gmv_for_aov = df['total_gmv'].sum()
        total_orders_for_aov = df['total_orders'].sum()
        avg_aov = total_gmv_for_aov / total_orders_for_aov if total_orders_for_aov > 0 else 0.0
        st.metric(
            "平均客单价", 
            f"${avg_aov:.2f}",
            help="平均每个订单的金额 = 总销售额 ÷ 总订单数（USD）"
        )

    with col5:
        total_spend = df['total_spend'].sum()
        st.metric(
            "广告花费总额", 
            f"${total_spend:,.2f}",
            help="选择时间范围内的广告花费汇总（所有负责人）"
        )

    with col6:
        total_gmv_sum = df['total_gmv'].sum()
        total_roas = (total_gmv_sum / total_spend) if total_spend > 0 else None
        roas_display = "N/A" if total_roas is None else f"{total_roas:.2f}"
        st.metric(
            "总 ROAS", 
            roas_display,
            help="总销售额 ÷ 总广告花费；花费为0时显示 N/A"
        )
    
    with col7:
        total_orders_sum = df['total_orders'].sum()
        total_visitors_sum = df['total_visitors'].sum()
        if granularity == 'hour':
            # 按小时查看时，访客数需要按天去重后累加
            total_visitors_sum = df.groupby(df['time'].dt.date)['total_visitors'].max().sum()
        total_conversion_rate = (total_orders_sum / total_visitors_sum * 100) if total_visitors_sum > 0 else 0.0
        st.metric(
            "总转化率", 
            f"{total_conversion_rate:.2f}%",
            help="总订单数 ÷ 总访客数 × 100%；访客数为0时显示 0.00%"
        )
    
    # 折线图
    if st.session_state.selected_store == 'ALL_STORES':
        st.subheader("📈 数据趋势图（所有店铺聚合数据）")
    else:
        st.subheader(f"📈 数据趋势图（{st.session_state.selected_store_name}）")
    
    # 使用PyEcharts或Plotly绘制图表
    if use_pyecharts:
        # 确保 PyEcharts 模块已导入
        try:
            # 重新导入，确保在函数作用域内可用
            import pyecharts.options as opts
            from pyecharts.charts import Line as LineChart
            from pyecharts.commons.utils import JsCode
            
            # 准备图表数据（优化图表尺寸，提升使用体验）- 设置为800px高度
            # 使用更大的高度值确保图表显示清晰
            chart = LineChart(init_opts=opts.InitOpts(
                width="100%", 
                height="600px",  # 高度减少1/3（从880px减少到600px）
                renderer="canvas"
            ))
            
            # 准备颜色方案：主时间段使用实线，对比段使用虚线
            # 扩展颜色数组，支持最多4个对比段（每个4个指标）+ 主时间段（4个指标）= 20个颜色
            colors = [
                # 主时间段（4个指标）：蓝色系
                '#5470c6', '#91cc75', '#fac858', '#ee6666',
                # 对比段1（4个指标）：青色系
                '#73c0de', '#3ba272', '#fc8452', '#9a60b4',
                # 对比段2（4个指标）：橙色系
                '#ff9f40', '#ff6b9d', '#c44569', '#f8b500',
                # 对比段3（4个指标）：紫色系
                '#00d2d3', '#54a0ff', '#5f27cd', '#a55eea',
                # 对比段4（4个指标）：红色系
                '#ff6348', '#2ed573', '#1e90ff', '#ffa502'
            ]
            line_styles = ['solid', 'dashed', 'dotted', 'dashDot']
            
            # 检查是否启用对比模式
            if enable_compare and compare_data_list:
                # 对比模式：构建对齐的X轴
                # 判断对比类型：单天对比（按小时对齐）或多天对比（按天对齐）
                main_days = (end_datetime - start_datetime).days + 1
                is_single_day_compare = (main_days == 1 and granularity == 'hour')
                
                # 检查所有对比段是否也是单天
                if is_single_day_compare:
                    for compare_range in compare_ranges:
                        compare_days = (compare_range['end'] - compare_range['start']).days + 1
                        if compare_days != 1:
                            is_single_day_compare = False
                            break
                
                if is_single_day_compare and granularity == 'hour':
                    # 单天对比：根据时间段筛选生成小时列表
                    # 收集主时间段和所有对比段的时间段，取并集
                    hour_set = set()
                    
                    # 添加主时间段的小时
                    if start_hour is not None and end_hour is not None:
                        for h in range(start_hour, end_hour):
                            hour_set.add(h)
                    
                    # 添加所有对比段的时间段的小时
                    for compare_range in compare_ranges:
                        cmp_start_hour = compare_range.get('start_hour')
                        cmp_end_hour = compare_range.get('end_hour')
                        if cmp_start_hour is not None and cmp_end_hour is not None:
                            for h in range(cmp_start_hour, cmp_end_hour):
                                hour_set.add(h)
                    
                    # 如果没有任何时间段筛选，默认使用所有24小时
                    if not hour_set:
                        hour_set = set(range(24))
                    
                    # 按小时排序生成时间列表
                    sorted_hours = sorted(hour_set)
                    all_times = [pd.Timestamp(st.session_state.start_date) + pd.Timedelta(hours=h) for h in sorted_hours]
                    xaxis_labels = [f"{h:02d}:00" for h in sorted_hours]
                else:
                    # 多天对比或天粒度对比：按索引位置对齐
                    # 计算最短的天数，作为对齐基准
                    min_days = main_days
                    for compare_range in compare_ranges:
                        compare_days = (compare_range['end'] - compare_range['start']).days + 1
                        min_days = min(min_days, compare_days)
                    
                    if granularity == 'hour':
                        # 按天分组，每天取对应的小时数据（只包含主时间段和对比段的时间段）
                        # 注意：hour_sets_by_date 在此处定义但未使用
                        # X轴生成使用的是 all_hours_set（所有小时的并集），而不是按日期分组的小时
                        # 此变量保留以便未来可能的扩展使用
                        hour_sets_by_date = {}  # {date: set(hours)} - 未使用，保留用于未来扩展
                        
                        # 主时间段的小时（保留用于未来扩展）
                        main_dates = sorted(df['time'].dt.date.unique())
                        for date in main_dates:
                            if date not in hour_sets_by_date:
                                hour_sets_by_date[date] = set()
                            if start_hour is not None and end_hour is not None:
                                for h in range(start_hour, end_hour):
                                    hour_sets_by_date[date].add(h)
                        
                        # 对比段的小时（按日期分组，保留用于未来扩展）
                        for compare_range in compare_ranges:
                            cmp_start = compare_range['start']
                            cmp_end = compare_range['end']
                            cmp_start_hour = compare_range.get('start_hour')
                            cmp_end_hour = compare_range.get('end_hour')
                            
                            # 遍历对比段的每一天
                            current_date = cmp_start
                            while current_date <= cmp_end:
                                if current_date not in hour_sets_by_date:
                                    hour_sets_by_date[current_date] = set()
                                if cmp_start_hour is not None and cmp_end_hour is not None:
                                    for h in range(cmp_start_hour, cmp_end_hour):
                                        hour_sets_by_date[current_date].add(h)
                                current_date += timedelta(days=1)
                        
                        # 生成时间列表
                        # 1. 收集所有需要的小时（主时间段和对比段的时间段并集）
                        all_hours_set = set()
                        if start_hour is not None and end_hour is not None:
                            for h in range(start_hour, end_hour):
                                all_hours_set.add(h)
                        for compare_range in compare_ranges:
                            cmp_start_hour = compare_range.get('start_hour')
                            cmp_end_hour = compare_range.get('end_hour')
                            if cmp_start_hour is not None and cmp_end_hour is not None:
                                for h in range(cmp_start_hour, cmp_end_hour):
                                    all_hours_set.add(h)
                        
                        # 2. 如果没有时间段筛选，默认使用所有24小时
                        if not all_hours_set:
                            all_hours_set = set(range(24))
                        
                        # 3. 为每个主时间段的日期生成时间点（包含所有需要的小时）
                        all_times = []
                        sorted_all_hours = sorted(all_hours_set)
                        for day_offset in range(min_days):
                            if day_offset < len(main_dates):
                                base_date = main_dates[day_offset]
                                for hour in sorted_all_hours:
                                    all_times.append(pd.Timestamp(base_date) + pd.Timedelta(hours=hour))
                        
                        xaxis_labels = [t.strftime('%m月%d日 %H:%M') for t in all_times]
                    else:
                        # 天粒度：按天数对齐
                        main_dates = sorted(df['time'].dt.date.unique())[:min_days]
                        all_times = [pd.Timestamp(d) for d in main_dates]
                        xaxis_labels = [t.strftime('%m月%d日') for t in all_times]
            else:
                # 非对比模式：使用主时间段的时间轴
                if granularity == 'hour':
                    xaxis_labels = [t.strftime('%m月%d日 %H:%M') for t in df['time']]
                else:
                    # 统一使用 %m月%d日 格式，与对比模式保持一致，确保tooltip formatter能正确解析
                    xaxis_labels = [t.strftime('%m月%d日') for t in df['time']]
                all_times = df['time'].tolist()
            
            chart.add_xaxis(xaxis_labels)
            
            # 扩展第二个Y轴（右轴：数量）- 必须在添加数据之前调用
            chart.extend_axis(
                yaxis=opts.AxisOpts(
                    name="数量（订单数/访客数）",
                    position="right",
                    type_="value",
                    name_location="middle",
                    name_gap=35,  # 减小边距，增加绘制区域宽度（从45减少到35，增加约10%绘制宽度）
                    name_textstyle_opts=opts.TextStyleOpts(font_size=14, font_weight="bold"),
                    axislabel_opts=opts.LabelOpts(font_size=12),
                    splitline_opts=opts.SplitLineOpts(is_show=False)
                )
            )
            
            # 辅助函数：对齐数据到统一的X轴
            def align_data_to_times(data_df, all_times_list, granularity_mode, is_single_day_compare=False, main_dates_list=None,
                                    compare_start_hour=None, compare_end_hour=None):
                """
                将数据对齐到统一的时间轴
                
                Args:
                    data_df: 要对齐的数据DataFrame
                    all_times_list: 统一的时间轴列表（基于主时间段生成）
                    granularity_mode: 颗粒度模式（'hour' 或 'day'）
                    is_single_day_compare: 是否为单天对比
                    main_dates_list: 主时间段的日期列表（用于计算日期索引，可选）
                    compare_start_hour: 对比段的起始小时（可选，用于检查时间段）
                    compare_end_hour: 对比段的结束小时（可选，用于检查时间段）
                """
                aligned_data = {}
                if granularity_mode == 'hour':
                    if is_single_day_compare:
                        # 单天对比：按小时对齐（提取小时数）
                        for t in all_times_list:
                            hour = t.hour
                            # 在数据中查找对应小时的数据
                            matching = data_df[data_df['time'].dt.hour == hour]
                            if len(matching) > 0:
                                aligned_data[t] = matching.iloc[0]
                            else:
                                aligned_data[t] = None
                    else:
                        # 多天对比+小时颗粒度：按"日期索引+小时数"对齐
                        # 1. 从all_times中提取日期列表（用于确定日期索引）
                        dates_in_all_times = []
                        for t in all_times_list:
                            date = t.date()
                            if date not in dates_in_all_times:
                                dates_in_all_times.append(date)
                        
                        # 2. 将对比段数据按日期排序
                        compare_dates = sorted(data_df['time'].dt.date.unique())
                        
                        # 3. 为all_times中的每个时间点对齐数据
                        for t in all_times_list:
                            target_date = t.date()  # all_times中的日期（主时间段的日期）
                            target_hour = t.hour    # all_times中的小时数
                            
                            # 如果指定了对比段的时间段，检查target_hour是否在范围内
                            if compare_start_hour is not None and compare_end_hour is not None:
                                if not (compare_start_hour <= target_hour < compare_end_hour):
                                    # target_hour不在对比段的时间段内，返回None
                                    aligned_data[t] = None
                                    continue
                            
                            # 找到target_date在dates_in_all_times中的索引位置
                            if target_date in dates_in_all_times:
                                day_index = dates_in_all_times.index(target_date)
                                
                                # 在对比段数据中找到对应"日期索引+小时数"的数据
                                if day_index < len(compare_dates):
                                    compare_date = compare_dates[day_index]  # 对比段中对应索引的日期
                                    matching = data_df[
                                        (data_df['time'].dt.date == compare_date) & 
                                        (data_df['time'].dt.hour == target_hour)
                                    ]
                                    if len(matching) > 0:
                                        aligned_data[t] = matching.iloc[0]
                                        continue
                            
                            # 如果没有找到匹配的数据，返回None
                            aligned_data[t] = None
                else:
                    # 天粒度：按"日期索引"对齐
                    # 1. 从all_times中提取日期列表（用于确定日期索引）
                    dates_in_all_times = []
                    for t in all_times_list:
                        date = t.date()
                        if date not in dates_in_all_times:
                            dates_in_all_times.append(date)
                    
                    # 2. 将对比段数据按日期排序
                    compare_dates = sorted(data_df['time'].dt.date.unique())
                    
                    # 3. 为all_times中的每个日期对齐数据
                    for t in all_times_list:
                        target_date = t.date()  # all_times中的日期（主时间段的日期）
                        
                        # 找到target_date在dates_in_all_times中的索引位置
                        if target_date in dates_in_all_times:
                            day_index = dates_in_all_times.index(target_date)
                            
                            # 在对比段数据中找到对应"日期索引"的数据
                            if day_index < len(compare_dates):
                                compare_date = compare_dates[day_index]  # 对比段中对应索引的日期
                                matching = data_df[data_df['time'].dt.date == compare_date]
                                if len(matching) > 0:
                                    aligned_data[t] = matching.iloc[0]
                                    continue
                        
                        # 如果没有找到匹配的数据，返回None
                        aligned_data[t] = None
                return aligned_data
            
            # 添加主时间段的折线
            if enable_compare and compare_data_list:
                # 判断是否为单天对比
                main_days = (end_datetime - start_datetime).days + 1
                is_single_day = (main_days == 1 and granularity == 'hour' and 
                    all((compare_ranges[i]['end'] - compare_ranges[i]['start']).days == 0 
                    for i in range(len(compare_ranges))))
                
                # 对比模式：对齐数据并添加带日期标签的折线
                # 为主时间段对齐添加时间段参数，使逻辑更清晰一致
                aligned_main = align_data_to_times(
                    df, all_times, granularity, is_single_day,
                    compare_start_hour=start_hour,  # 主时间段的时间段
                    compare_end_hour=end_hour
                )
                
                # 优化标签显示
                if main_days == 1:
                    main_label_prefix = st.session_state.start_date.strftime('%Y-%m-%d')
                else:
                    main_label_prefix = f"{st.session_state.start_date.strftime('%Y-%m-%d')} 至 {st.session_state.end_date.strftime('%Y-%m-%d')}"
                
                if show_gmv:
                    chart.add_yaxis(
                        f"总销售额 ({main_label_prefix})",
                        [float(aligned_main[t]['total_gmv']) if aligned_main[t] is not None else 0 for t in all_times],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[0]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_orders:
                    chart.add_yaxis(
                        f"总订单数 ({main_label_prefix})",
                        [int(aligned_main[t]['total_orders']) if aligned_main[t] is not None else 0 for t in all_times],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[1]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_visitors:
                    chart.add_yaxis(
                        f"总访客数 ({main_label_prefix})",
                        [int(aligned_main[t]['total_visitors']) if aligned_main[t] is not None else 0 for t in all_times],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[2]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_aov:
                    chart.add_yaxis(
                        f"平均客单价 ({main_label_prefix})",
                        [float(aligned_main[t]['avg_order_value']) if aligned_main[t] is not None else 0 for t in all_times],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[3]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                if show_spend:
                    chart.add_yaxis(
                        f"广告花费 ({main_label_prefix})",
                        [float(aligned_main[t]['total_spend']) if aligned_main[t] is not None else 0 for t in all_times],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[4]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                if show_roas:
                    chart.add_yaxis(
                        f"ROAS ({main_label_prefix})",
                        [float(aligned_main[t]['roas']) if (aligned_main[t] is not None and aligned_main[t]['roas'] is not None and not np.isnan(aligned_main[t]['roas'])) else None for t in all_times],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[5]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
            else:
                # 非对比模式：直接添加折线（使用简洁的标签）
                if show_gmv:
                    chart.add_yaxis(
                        "总销售额 (total_gmv)",
                        [float(x) for x in df['total_gmv']],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[0]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_orders:
                    chart.add_yaxis(
                        "总订单数 (total_orders)",
                        [int(x) for x in df['total_orders']],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[1]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_visitors:
                    chart.add_yaxis(
                        "总访客数 (total_visitors)",
                        [int(x) for x in df['total_visitors']],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[2]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                
                if show_aov:
                    chart.add_yaxis(
                        "平均客单价 (avg_order_value)",
                        [float(x) for x in df['avg_order_value']],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[3]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                if show_spend:
                    chart.add_yaxis(
                        "广告花费 (total_spend)",
                        [float(x) for x in df['total_spend']],
                        yaxis_index=0,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[4]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
                if show_roas:
                    chart.add_yaxis(
                        "ROAS",
                        [float(x) if x is not None and not np.isnan(x) else None for x in df['roas']],
                        yaxis_index=1,
                        linestyle_opts=opts.LineStyleOpts(type_='solid', width=2),
                        itemstyle_opts=opts.ItemStyleOpts(color=colors[5]),
                        label_opts=opts.LabelOpts(is_show=False)
                    )
            
            # 添加对比段的折线（虚线）
            if enable_compare and compare_data_list:
                # 判断是否为单天对比
                main_days = (end_datetime - start_datetime).days + 1
                is_single_day = (main_days == 1 and granularity == 'hour' and 
                    all((compare_ranges[i]['end'] - compare_ranges[i]['start']).days == 0 
                    for i in range(len(compare_ranges))))
                
                # 计算yesterday用于快捷对比标签显示
                current_yesterday = (datetime.now() - timedelta(days=1)).date()
                
                for i, (compare_df, compare_range) in enumerate(zip(compare_data_list, compare_ranges)):
                    compare_start_hour = compare_range.get('start_hour')
                    compare_end_hour = compare_range.get('end_hour')
                    aligned_compare = align_data_to_times(
                        compare_df, all_times, granularity, is_single_day,
                        compare_start_hour=compare_start_hour,
                        compare_end_hour=compare_end_hour
                    )
                    
                    # 优化标签显示
                    compare_days = (compare_range['end'] - compare_range['start']).days + 1
                    
                    # 检查是否是快捷对比
                    is_quick_compare = False
                    compare_label_prefix = ""
                    
                    if 'quick_compare_range' in st.session_state:
                        for qr in st.session_state.quick_compare_range:
                            if (qr['start'] == compare_range['start'] and 
                                qr['end'] == compare_range['end']):
                                is_quick_compare = True
                                # 快捷对比：显示具体日期范围（与普通对比模式保持一致）
                                if compare_days == 1:
                                    # 单天对比：显示具体日期
                                    compare_label_prefix = compare_range['start'].strftime('%Y-%m-%d') + "（对比）"
                                else:
                                    # 多天对比：显示日期范围
                                    compare_label_prefix = f"{compare_range['start'].strftime('%Y-%m-%d')} 至 {compare_range['end'].strftime('%Y-%m-%d')}（对比）"
                                break
                    
                    if not is_quick_compare:
                        # 普通对比，使用默认标签
                        if compare_days == 1:
                            compare_label_prefix = compare_range['start'].strftime('%Y-%m-%d')
                        else:
                            compare_label_prefix = f"{compare_range['start'].strftime('%Y-%m-%d')} 至 {compare_range['end'].strftime('%Y-%m-%d')}"
                    color_offset = (i + 1) * 4  # 每个对比段使用不同的颜色组
                    line_style = line_styles[(i + 1) % len(line_styles)]  # 循环使用线型
                    
                    # 为tooltip准备日期映射信息（在series name中嵌入，用特殊分隔符）
                    compare_start_date_str = compare_range['start'].strftime('%Y-%m-%d')
                    main_start_date_str = st.session_state.start_date.strftime('%Y-%m-%d')
                    
                    if show_gmv:
                        chart.add_yaxis(
                            f"总销售额 ({compare_label_prefix})|对比开始|{compare_start_date_str}|主开始|{main_start_date_str}",
                            [float(aligned_compare[t]['total_gmv']) if aligned_compare[t] is not None else 0 for t in all_times],
                            yaxis_index=0,
                            linestyle_opts=opts.LineStyleOpts(type_=line_style, width=2),
                            itemstyle_opts=opts.ItemStyleOpts(color=colors[color_offset % len(colors)]),
                            label_opts=opts.LabelOpts(is_show=False)
                        )
                    
                    if show_orders:
                        chart.add_yaxis(
                            f"总订单数 ({compare_label_prefix})|对比开始|{compare_start_date_str}|主开始|{main_start_date_str}",
                            [int(aligned_compare[t]['total_orders']) if aligned_compare[t] is not None else 0 for t in all_times],
                            yaxis_index=1,
                            linestyle_opts=opts.LineStyleOpts(type_=line_style, width=2),
                            itemstyle_opts=opts.ItemStyleOpts(color=colors[(color_offset + 1) % len(colors)]),
                            label_opts=opts.LabelOpts(is_show=False)
                        )
                    
                    if show_visitors:
                        chart.add_yaxis(
                            f"总访客数 ({compare_label_prefix})|对比开始|{compare_start_date_str}|主开始|{main_start_date_str}",
                            [int(aligned_compare[t]['total_visitors']) if aligned_compare[t] is not None else 0 for t in all_times],
                            yaxis_index=1,
                            linestyle_opts=opts.LineStyleOpts(type_=line_style, width=2),
                            itemstyle_opts=opts.ItemStyleOpts(color=colors[(color_offset + 2) % len(colors)]),
                            label_opts=opts.LabelOpts(is_show=False)
                        )
                    
                    if show_aov:
                        chart.add_yaxis(
                            f"平均客单价 ({compare_label_prefix})|对比开始|{compare_start_date_str}|主开始|{main_start_date_str}",
                            [float(aligned_compare[t]['avg_order_value']) if aligned_compare[t] is not None else 0 for t in all_times],
                            yaxis_index=0,
                            linestyle_opts=opts.LineStyleOpts(type_=line_style, width=2),
                            itemstyle_opts=opts.ItemStyleOpts(color=colors[(color_offset + 3) % len(colors)]),
                            label_opts=opts.LabelOpts(is_show=False)
                        )
            
            # 计算数据天数（包含对比段）
            total_days = (end_datetime - start_datetime).days + 1
            if enable_compare and compare_ranges:
                for compare_range in compare_ranges:
                    compare_days = (datetime.combine(compare_range['end'], datetime.max.time()) - 
                                  datetime.combine(compare_range['start'], datetime.min.time())).days + 1
                    total_days = max(total_days, compare_days)
            
            # 配置第一个Y轴（左轴：金额/客单价）
            yaxis_left = opts.AxisOpts(
                name="金额/客单价（单位：USD）",
                position="left",
                name_location="middle",
                name_gap=35,  # 减小边距，增加绘制区域宽度（从45减少到35，增加约10%绘制宽度）
                name_textstyle_opts=opts.TextStyleOpts(font_size=12, font_weight="bold"),
                axislabel_opts=opts.LabelOpts(font_size=10),
                splitline_opts=opts.SplitLineOpts(is_show=True, linestyle_opts=opts.LineStyleOpts(opacity=0.3))
            )
            
            # 增强tooltip格式化函数，支持显示对比时间段对应的具体日期
            # 简化tooltip formatter，避免所有可能的语法问题
            # 优化后的简化版tooltip formatter，避免代码被截断
            # 完整功能的tooltip formatter，实现所有需求
            # 压缩JavaScript代码为单行，避免JSON序列化问题
            tooltip_formatter = """function(params){if(!params)return '';var result='';var colon=String.fromCharCode(58);var timeStr='';var mainItems=[];var compareItems=[];var compareTimeStr='';function getValue(value){if(value===null||value===undefined)return 0;if(Array.isArray(value)){return value.length>1?value[1]:value[0];}return value;}function formatCurrency(value){var num=parseFloat(getValue(value))||0;var dollarSign=String.fromCharCode(36);return dollarSign+num.toFixed(2);}function formatNumber(value){var num=parseFloat(getValue(value))||0;if(num>=1000){return num.toLocaleString('en-US');}return num.toString();}function parseAxisTime(axisValue){var month=0,day=0,hour=null;var yueIndex=axisValue.indexOf('月');var riIndex=axisValue.indexOf('日');if(yueIndex>0&&riIndex>yueIndex){var monthStart=yueIndex-2<0?0:yueIndex-2;month=parseInt(axisValue.substring(monthStart,yueIndex))||0;var dayStart=riIndex-2<yueIndex+1?yueIndex+1:riIndex-2;day=parseInt(axisValue.substring(dayStart,riIndex))||0;var colonIndex=axisValue.indexOf(String.fromCharCode(58),riIndex);if(colonIndex>riIndex){var hourStr=axisValue.substring(colonIndex-2,colonIndex).trim();hour=parseInt(hourStr)||null;}}var resultObj={};resultObj['month']=month;resultObj['day']=day;resultObj['hour']=hour;return resultObj;}function calcCompareTime(axisValue,compareStartDate,mainStartDate){var axisTime=parseAxisTime(axisValue);if(!axisTime.month||!axisTime.day)return null;var mainParts=mainStartDate.split('-');var compareParts=compareStartDate.split('-');if(mainParts.length!==3||compareParts.length!==3)return null;var mainDate=new Date(parseInt(mainParts[0]),parseInt(mainParts[1])-1,parseInt(mainParts[2]));var compareDate=new Date(parseInt(compareParts[0]),parseInt(compareParts[1])-1,parseInt(compareParts[2]));var mainTargetDate=new Date(mainDate.getFullYear(),axisTime.month-1,axisTime.day);if(mainTargetDate<mainDate){mainTargetDate.setFullYear(mainTargetDate.getFullYear()+1);}var dayDiff=Math.floor((mainTargetDate-mainDate)/(1000*60*60*24));var resultDate=new Date(compareDate);resultDate.setDate(resultDate.getDate()+dayDiff);var month=resultDate.getMonth()+1;var day=resultDate.getDate();var result=month+'月'+day+'日';if(axisTime.hour!==null){var hourStr=axisTime.hour<10?'0'+axisTime.hour:axisTime.hour.toString();result+=' '+hourStr+String.fromCharCode(58)+'00';}return result;}if(params instanceof Array&&params.length>0){if(params[0].axisValue){timeStr=params[0].axisValue;}for(var i=0;i<params.length;i++){var item=params[i];if(item&&item.seriesName&&item.value!==undefined){var name=item.seriesName;var isCompare=false;var displayName='';var dateRange='';var compareStartDate='';var mainStartDate='';if(name.indexOf('|')>0){var parts=name.split('|');displayName=parts[0].trim();var rangeStart=displayName.indexOf('(');var rangeEnd=displayName.indexOf(')');if(rangeStart>0&&rangeEnd>rangeStart){dateRange=displayName.substring(rangeStart,rangeEnd+1);displayName=displayName.substring(0,rangeStart).trim();}for(var j=1;j<parts.length;j++){if(parts[j].trim()==='对比开始'&&j+1<parts.length){isCompare=true;compareStartDate=parts[j+1].trim();if(j+3<parts.length&&parts[j+2].trim()==='主开始'){mainStartDate=parts[j+3].trim();}break;}}}else{displayName=name.trim();}var newItem={};newItem['name']=displayName;newItem['dateRange']=dateRange;newItem['value']=getValue(item.value);newItem['marker']=item.marker||'';newItem['isCurrency']=displayName.indexOf('销售额')>=0||displayName.indexOf('客单价')>=0;newItem['compareStartDate']=compareStartDate;newItem['mainStartDate']=mainStartDate;if(isCompare){compareItems.push(newItem);if(!compareTimeStr&&timeStr&&compareStartDate&&mainStartDate){compareTimeStr=calcCompareTime(timeStr,compareStartDate,mainStartDate);}}else{mainItems.push(newItem);}}}if(timeStr){result+='时间'+colon+' '+timeStr+'<br/>';}if(mainItems.length>0){result+='<b>主时间段'+colon+'</b><br/>';for(var i=0;i<mainItems.length;i++){var item=mainItems[i];var valueStr=item.isCurrency?formatCurrency(item.value):formatNumber(item.value);var displayText=item.name+(item.dateRange?' '+item.dateRange:'');result+=item.marker+displayText+colon+' '+valueStr+'<br/>';}}if(compareItems.length>0){if(mainItems.length>0){result+='<br/>';}if(compareTimeStr){result+='时间'+colon+' '+compareTimeStr+'<br/>';}result+='<b>对比时间段'+colon+'</b><br/>';for(var i=0;i<compareItems.length;i++){var item=compareItems[i];var valueStr=item.isCurrency?formatCurrency(item.value):formatNumber(item.value);var displayText=item.name+(item.dateRange?' '+item.dateRange:'');result+=item.marker+displayText+colon+' '+valueStr+'<br/>';}}}else if(params.axisValue){result='时间'+colon+' '+params.axisValue+'<br/>';if(params.seriesName&&params.value!==undefined){var name=params.seriesName.split('|')[0].trim();var isCurrency=name.indexOf('销售额')>=0||name.indexOf('客单价')>=0;var valueStr=isCurrency?formatCurrency(getValue(params.value)):formatNumber(getValue(params.value));result+=(params.marker||'')+name+colon+' '+valueStr;}}return result;}"""
            
            # 构建标题
            if enable_compare and compare_ranges:
                title_text = f"数据趋势图（主时间段+{len(compare_ranges)}个对比段）"
            else:
                title_text = f"数据趋势图（共{total_days}天数据）"
            
            chart.set_global_opts(
                title_opts=opts.TitleOpts(
                    title=title_text,
                    title_textstyle_opts=opts.TextStyleOpts(font_size=14)
                ),
                tooltip_opts=opts.TooltipOpts(
                    trigger="axis",
                    axis_pointer_type="cross",
                    formatter=JsCode(tooltip_formatter)
                ),
                legend_opts=opts.LegendOpts(
                    pos_top="5%",
                    orient="horizontal",
                    textstyle_opts=opts.TextStyleOpts(font_size=14),
                    item_width=30,
                    item_height=16
                ),
                datazoom_opts=[
                    opts.DataZoomOpts(
                        type_="inside",
                        range_start=0,
                        range_end=100
                    ),
                    opts.DataZoomOpts(
                        type_="slider",
                        range_start=0,
                        range_end=100,
                        pos_bottom="2%",  # 进度条放在最底部（距离底部2%）
                        filter_mode="none"  # 不进行数据过滤，保持原始数据
                    )
                ],
                xaxis_opts=opts.AxisOpts(
                    name=f"时间轴（{'小时模式：显示每个小时的数据点' if granularity == 'hour' else '天模式：显示每天的数据汇总'}）",
                    name_location="middle",
                    name_gap=80 if granularity == 'hour' else 50,  # X轴名称位置，为标签留出空间
                    name_textstyle_opts=opts.TextStyleOpts(font_size=14, font_weight="bold"),
                    axislabel_opts=opts.LabelOpts(
                        rotate=45 if granularity == 'hour' else 0,
                        font_size=11,
                        margin=30,  # 标签与轴线的距离，增加以确保标签完全显示
                        interval=0 if granularity == 'hour' else 'auto'  # 小时模式显示所有标签
                    ),
                    boundary_gap=True  # 两边留白，避免标签贴边
                ),
                yaxis_opts=yaxis_left
            )
            
            # 使用 render_embed() 方法将图表渲染为 HTML 字符串，然后通过 st.components.v1.html 渲染
            # 这样可以完全控制图表高度，不受 streamlit-echarts 组件的限制
            chart_html = chart.render_embed()
            
            # 使用 html() 组件渲染图表，显式设置高度为 600px（高度减少1/3）
            html(chart_html, height=600, scrolling=False)
        except Exception as e:
            # 如果导入失败，使用 Streamlit 原生图表（优化中文显示）
            import traceback
            error_detail = traceback.format_exc()
            st.warning(f"⚠️ PyEcharts 渲染失败，使用原生图表")
            with st.expander("🔍 查看错误详情（点击展开）", expanded=False):
                st.code(f"错误类型: {type(e).__name__}\n错误信息: {str(e)}\n\n详细堆栈:\n{error_detail}", language="python")
            
            # 准备数据，使用中文列名（修复X轴显示问题）
            chart_df = df.copy()
            # 确保time列是datetime类型
            if 'time' in chart_df.columns:
                chart_df['time'] = pd.to_datetime(chart_df['time'])
                # 格式化时间用于X轴显示（必须转换为字符串，不能用datetime索引）
                if granularity == 'hour':
                    chart_df['time_display'] = chart_df['time'].dt.strftime('%m月%d日 %H:%M')
                else:
                    chart_df['time_display'] = chart_df['time'].dt.strftime('%Y年%m月%d日')
                # 使用字符串索引，确保X轴正确显示
                chart_df = chart_df.set_index('time_display', drop=True)
            elif 'time' not in chart_df.index.names:
                # 如果没有time列，尝试从索引获取
                if hasattr(chart_df.index, 'strftime'):
                    if granularity == 'hour':
                        chart_df.index = pd.to_datetime(chart_df.index).strftime('%m月%d日 %H:%M')
                    else:
                        chart_df.index = pd.to_datetime(chart_df.index).strftime('%Y年%m月%d日')
            
            chart_columns = []
            chart_labels = {}
            
            if show_gmv:
                chart_columns.append('total_gmv')
                chart_labels['total_gmv'] = '总销售额 (total_gmv)'
            if show_orders:
                chart_columns.append('total_orders')
                chart_labels['total_orders'] = '总订单数 (total_orders)'
            if show_visitors:
                chart_columns.append('total_visitors')
                chart_labels['total_visitors'] = '总访客数 (total_visitors)'
            if show_aov:
                chart_columns.append('avg_order_value')
                chart_labels['avg_order_value'] = '平均客单价 (avg_order_value)'
            if show_spend:
                chart_columns.append('total_spend')
                chart_labels['total_spend'] = '广告花费 (total_spend)'
            if show_roas:
                chart_columns.append('roas')
                chart_labels['roas'] = 'ROAS'
            
            # 重命名列为中文
            chart_df_display = chart_df[chart_columns].rename(columns=chart_labels)
            
            # 显示图表（原生图表会显示中文列名）
            st.line_chart(chart_df_display, height=800)
            
            # 添加说明
            st.caption("💡 提示：当前使用Streamlit原生图表。如需更好的图表体验，请确保已安装 pyecharts 和 streamlit-echarts")
    else:
        # 如果PyEcharts不可用，使用Streamlit原生图表
        chart_df = df.set_index('time')
        chart_columns = []
        chart_labels = {}  # 列名映射到中文标签
        
        if show_gmv:
            chart_columns.append('total_gmv')
            chart_labels['total_gmv'] = '总销售额 (total_gmv)'
        if show_orders:
            chart_columns.append('total_orders')
            chart_labels['total_orders'] = '总订单数 (total_orders)'
        if show_visitors:
            chart_columns.append('total_visitors')
            chart_labels['total_visitors'] = '总访客数 (total_visitors)'
        if show_aov:
            chart_columns.append('avg_order_value')
            chart_labels['avg_order_value'] = '平均客单价 (avg_order_value)'
        if show_spend:
            chart_columns.append('total_spend')
            chart_labels['total_spend'] = '广告花费 (total_spend)'
        if show_roas:
            chart_columns.append('roas')
            chart_labels['roas'] = 'ROAS'
        
        # 重命名列以显示中文标签
        chart_df_display = chart_df[chart_columns].rename(columns=chart_labels)
        st.line_chart(chart_df_display, height=800)
    
    # 确保必须列存在，避免空列触发 KeyError
    required_cols = ['time', 'total_gmv', 'total_orders', 'total_visitors', 'avg_order_value', 'total_spend', 'roas']
    for col in required_cols:
        if col not in df.columns:
            if col == 'time':
                df[col] = pd.to_datetime(df['date']) if 'date' in df.columns else pd.NaT
            elif col in ['avg_order_value', 'total_spend', 'total_gmv']:
                df[col] = 0.0
            elif col in ['roas']:
                df[col] = np.nan
            else:
                df[col] = 0
    
    # 数据表格
    with st.expander("📋 查看详细数据"):
        # 准备表格数据，使用中文列名
        table_df = df[['time', 'total_gmv', 'total_orders', 'total_visitors', 'avg_order_value', 'total_spend', 'roas']].copy()
        
        # 格式化时间列
        if granularity == 'hour':
            table_df['time'] = pd.to_datetime(table_df['time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            table_df['time'] = pd.to_datetime(table_df['time']).dt.strftime('%Y-%m-%d')
        
        # 重命名列为中文
        table_df.columns = ['时间', '总销售额 (USD)', '总订单数', '总访客数', '平均客单价 (USD)', '广告花费 (USD)', 'ROAS']
        
        # 格式化显示（金额保留2位小数）
        display_df = table_df.copy()
        display_df['总销售额 (USD)'] = display_df['总销售额 (USD)'].apply(lambda x: f"${float(x):.2f}")
        display_df['平均客单价 (USD)'] = display_df['平均客单价 (USD)'].apply(lambda x: f"${float(x):.2f}")
        display_df['广告花费 (USD)'] = display_df['广告花费 (USD)'].apply(lambda x: f"${float(x):.2f}")
        display_df['ROAS'] = display_df['ROAS'].apply(lambda x: "N/A" if pd.isna(x) else f"{float(x):.2f}")
        
        st.dataframe(display_df, use_container_width=True)
        
        # 导出CSV（使用原始数据，保持数值格式）
        csv = table_df.to_csv(index=False)
        st.download_button(
            label="📥 导出CSV",
            data=csv,
            file_name=f"shoplazza_data_{st.session_state.start_date}_{st.session_state.end_date}.csv",
            mime="text/csv"
        )
    
    # 管理员功能（手动同步数据功能已移除，数据更新请直接在数据库执行命令）
    
    # 负责人数据列表区域
    render_owner_summary_section()


@st.dialog("负责人小时趋势", width="large")
def show_owner_modal(owner_name: str, start_date: date, end_date: date):
    """显示负责人的小时趋势弹窗"""
    import database as db_module
    
    # 获取数据
    popup_start_dt = datetime.combine(start_date, datetime.min.time())
    popup_end_dt = datetime.combine(end_date, datetime.max.time())
    
    db = db_module.Database()
    hourly_data = db.get_owner_hourly_data(owner_name, popup_start_dt, popup_end_dt)
    
    if not hourly_data:
        st.warning(f"📭 {owner_name} 在所选时间段内暂无数据")
        return
    
    df_popup = pd.DataFrame(hourly_data)
    df_popup['time'] = pd.to_datetime(df_popup['time_hour'])
    
    # 确保列存在
    for col in ['total_gmv', 'total_orders', 'total_visitors', 'avg_order_value', 'total_spend', 'tt_total_spend', 'total_spend_all', 'roas', 'conversion_rate']:
        if col not in df_popup.columns:
            df_popup[col] = 0.0
    
    # 显示标题和日期范围
    st.markdown(f"**负责人：** {owner_name}")
    st.caption(f"日期范围：{start_date} ~ {end_date}")
    st.divider()
    
    # 指标选择（使用 session_state 保存状态）
    metric_key_prefix = f"owner_modal_{owner_name}_"
    if f"{metric_key_prefix}gmv" not in st.session_state:
        st.session_state[f"{metric_key_prefix}gmv"] = True
        st.session_state[f"{metric_key_prefix}fb_spend"] = True
        st.session_state[f"{metric_key_prefix}tt_spend"] = True
        st.session_state[f"{metric_key_prefix}roas"] = True
        st.session_state[f"{metric_key_prefix}orders"] = False
        st.session_state[f"{metric_key_prefix}aov"] = False
    
    st.markdown("**选择显示的指标：**")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        show_gmv = st.checkbox("销售额", value=st.session_state[f"{metric_key_prefix}gmv"], key=f"{metric_key_prefix}chk_gmv")
    with col2:
        show_orders = st.checkbox("订单数", value=st.session_state[f"{metric_key_prefix}orders"], key=f"{metric_key_prefix}chk_orders")
    with col3:
        show_fb_spend = st.checkbox("Facebook广告花费", value=st.session_state[f"{metric_key_prefix}fb_spend"], key=f"{metric_key_prefix}chk_fb_spend")
    with col4:
        show_tt_spend = st.checkbox("TikTok广告花费", value=st.session_state[f"{metric_key_prefix}tt_spend"], key=f"{metric_key_prefix}chk_tt_spend")
    with col5:
        show_aov = st.checkbox("客单价", value=st.session_state[f"{metric_key_prefix}aov"], key=f"{metric_key_prefix}chk_aov")
    with col6:
        show_roas = st.checkbox("ROAS", value=st.session_state[f"{metric_key_prefix}roas"], key=f"{metric_key_prefix}chk_roas")
    with col7:
        show_conversion = st.checkbox("转化率", value=st.session_state.get(f"{metric_key_prefix}conversion", False), key=f"{metric_key_prefix}chk_conversion")
    
    # 更新 session_state
    st.session_state[f"{metric_key_prefix}gmv"] = show_gmv
    st.session_state[f"{metric_key_prefix}fb_spend"] = show_fb_spend
    st.session_state[f"{metric_key_prefix}tt_spend"] = show_tt_spend
    st.session_state[f"{metric_key_prefix}roas"] = show_roas
    st.session_state[f"{metric_key_prefix}orders"] = show_orders
    st.session_state[f"{metric_key_prefix}aov"] = show_aov
    st.session_state[f"{metric_key_prefix}conversion"] = show_conversion
    
    # 准备图表数据
    chart_df = df_popup.copy()
    chart_df['time_str'] = chart_df['time'].dt.strftime('%Y-%m-%d %H:%M')
    chart_df = chart_df.sort_values('time')
    
    # 计算转化率（如果订单数或访客数存在）
    if 'total_orders' in chart_df.columns and 'total_visitors' in chart_df.columns:
        chart_df['conversion_rate'] = chart_df.apply(
            lambda row: (row['total_orders'] / row['total_visitors'] * 100) if row['total_visitors'] > 0 else 0.0,
            axis=1
        )
    elif 'conversion_rate' not in chart_df.columns:
        chart_df['conversion_rate'] = 0.0
    
    # 选择要显示的列
    chart_columns = []
    if show_gmv:
        chart_columns.append(('total_gmv', '销售额'))
    if show_orders:
        chart_columns.append(('total_orders', '订单数'))
    if show_fb_spend:
        chart_columns.append(('total_spend', 'Facebook广告花费'))
    if show_tt_spend:
        chart_columns.append(('tt_total_spend', 'TikTok广告花费'))
    if show_aov:
        chart_columns.append(('avg_order_value', '客单价'))
    if show_roas:
        chart_columns.append(('roas', 'ROAS'))
    if show_conversion:
        chart_columns.append(('conversion_rate', '转化率'))
    
    if not chart_columns:
        st.info("请至少选择一个指标")
    else:
        # 使用 PyEcharts 绘制折线图（如果可用）
        if use_pyecharts:
            line = Line(init_opts=opts.InitOpts(width="100%", height="400px"))
            line.add_xaxis(chart_df['time_str'].tolist())
            
            colors = {
                'total_gmv': '#5470c6',
                'total_orders': '#fac858',
                'total_spend': '#ee6666',  # Facebook广告花费 - 红色
                'tt_total_spend': '#ff6b9d',  # TikTok广告花费 - 粉色
                'avg_order_value': '#73c0de',
                'roas': '#91cc75',
                'conversion_rate': '#fc8452'  # 转化率 - 橙色
            }
            
            for col, label in chart_columns:
                values = chart_df[col].fillna(0).tolist()
                line.add_yaxis(
                    series_name=label,
                    y_axis=values,
                    is_smooth=True,
                    linestyle_opts=opts.LineStyleOpts(width=2),
                    itemstyle_opts=opts.ItemStyleOpts(color=colors.get(col, '#5470c6')),
                    label_opts=opts.LabelOpts(is_show=False),
                )
            
            line.set_global_opts(
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                legend_opts=opts.LegendOpts(pos_top="10%"),
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    axislabel_opts=opts.LabelOpts(rotate=45, interval=0)
                ),
                yaxis_opts=opts.AxisOpts(
                    type_="value",
                    splitline_opts=opts.SplitLineOpts(is_show=True)
                ),
            )
            
            st_pyecharts(line, height=400)
        else:
            # 使用 Streamlit 原生折线图
            chart_data = chart_df.set_index('time_str')
            display_data = pd.DataFrame()
            for col, label in chart_columns:
                display_data[label] = chart_df[col].fillna(0)
            display_data.index = chart_df['time_str']
            
            st.line_chart(display_data, height=400)
    
    st.divider()
    
    # 显示数据表格
    st.markdown("**小时明细数据：**")
    display_table = df_popup.copy()
    display_table['时间'] = display_table['time'].dt.strftime('%Y-%m-%d %H:%M')
    display_table['销售额 (USD)'] = display_table['total_gmv'].apply(lambda x: f"${float(x):,.2f}")
    display_table['订单数'] = display_table['total_orders'].apply(lambda x: f"{int(x):,}")
    display_table['访客数'] = display_table['total_visitors'].apply(lambda x: f"{int(x):,}")
    display_table['客单价 (USD)'] = display_table['avg_order_value'].apply(lambda x: f"${float(x):,.2f}")
    display_table['Facebook广告花费 (USD)'] = display_table['total_spend'].apply(lambda x: f"${float(x):,.2f}")
    display_table['TikTok广告花费 (USD)'] = display_table['tt_total_spend'].apply(lambda x: f"${float(x):,.2f}")
    display_table['总广告花费 (USD)'] = display_table['total_spend_all'].apply(lambda x: f"${float(x):,.2f}")
    display_table['ROAS'] = display_table['roas'].apply(lambda x: "N/A" if pd.isna(x) else f"{float(x):.2f}")
    # 计算转化率
    if 'total_orders' in display_table.columns and 'total_visitors' in display_table.columns:
        display_table['转化率'] = display_table.apply(
            lambda row: f"{(row['total_orders'] / row['total_visitors'] * 100):.2f}%" if row['total_visitors'] > 0 else "0.00%",
            axis=1
        )
    else:
        display_table['转化率'] = "0.00%"
    
    table_columns = ['时间', '销售额 (USD)', '订单数', '访客数', '客单价 (USD)', 'Facebook广告花费 (USD)', 'TikTok广告花费 (USD)', '总广告花费 (USD)', 'ROAS', '转化率']
    st.dataframe(
        display_table[table_columns],
        use_container_width=True,
        hide_index=True,
        height=300
    )


def render_owner_summary_section():
    """负责人汇总 + 小时趋势"""
    st.divider()
    st.subheader("👤 各负责人数据汇总（按日聚合）")
    
    # 映射编辑功能（可折叠）
    with st.expander("⚙️ 编辑映射（店铺/广告账户 → 负责人）", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        # 店铺映射编辑
        with col1:
            st.markdown("**📦 店铺 → 负责人映射**")
            store_mappings = db.get_store_owner_mappings()
            if store_mappings:
                # 使用表格形式展示，更简洁
                for mapping in store_mappings:
                    with st.container():
                        new_owner = st.text_input(
                            f"店铺: {mapping['shop_domain']}",
                            value=mapping['owner'],
                            key=f"store_owner_{mapping['id']}",
                            help="修改负责人后点击保存"
                        )
                        if new_owner != mapping['owner']:
                            if st.button("💾 保存", key=f"save_store_{mapping['id']}", use_container_width=True):
                                # 更新映射并获取受影响的日期
                                affected_dates = db.update_store_owner_mapping(mapping['shop_domain'], new_owner)
                                if affected_dates is not None:
                                    st.info(f"🔄 正在重新聚合 {len(affected_dates)} 个日期的数据...")
                                    # 重新聚合受影响日期的数据
                                    if db.aggregate_owner_daily_for_dates(affected_dates):
                                        st.success(f"✅ 已更新: {mapping['shop_domain']} -> {new_owner}，并重新聚合了 {len(affected_dates)} 个日期的数据")
                                    else:
                                        st.warning(f"⚠️ 映射已更新，但重新聚合失败，请手动运行聚合脚本")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 更新失败: {mapping['shop_domain']}")
            else:
                st.info("暂无店铺映射数据")
        
        # Facebook广告账户映射编辑
        with col2:
            st.markdown("**📢 Facebook广告账户 → 负责人映射**")
            ad_mappings = db.get_ad_account_owner_mappings()
            if ad_mappings:
                # 使用表格形式展示，更简洁
                for mapping in ad_mappings:
                    with st.container():
                        new_owner = st.text_input(
                            f"账户: {mapping['ad_account_id']}",
                            value=mapping['owner'],
                            key=f"ad_owner_{mapping['id']}",
                            help="修改负责人后点击保存"
                        )
                        if new_owner != mapping['owner']:
                            if st.button("💾 保存", key=f"save_ad_{mapping['id']}", use_container_width=True):
                                # 更新映射并获取受影响的日期
                                affected_dates = db.update_ad_account_owner_mapping(mapping['ad_account_id'], new_owner)
                                if affected_dates is not None:
                                    st.info(f"🔄 正在重新聚合 {len(affected_dates)} 个日期的数据...")
                                    # 重新聚合受影响日期的数据
                                    if db.aggregate_owner_daily_for_dates(affected_dates):
                                        st.success(f"✅ 已更新: {mapping['ad_account_id']} -> {new_owner}，并重新聚合了 {len(affected_dates)} 个日期的数据")
                                    else:
                                        st.warning(f"⚠️ 映射已更新，但重新聚合失败，请手动运行聚合脚本")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 更新失败: {mapping['ad_account_id']}")
            else:
                st.info("暂无Facebook广告账户映射数据")
        
        # TikTok广告账户映射编辑
        with col3:
            st.markdown("**🎵 TikTok广告账户 → 负责人映射**")
            tt_ad_mappings = db.get_tt_ad_account_owner_mappings()
            if tt_ad_mappings:
                # 使用表格形式展示，更简洁
                for mapping in tt_ad_mappings:
                    with st.container():
                        new_owner = st.text_input(
                            f"账户: {mapping['ad_account_id']}",
                            value=mapping['owner'],
                            key=f"tt_ad_owner_{mapping['id']}",
                            help="修改负责人后点击保存"
                        )
                        if new_owner != mapping['owner']:
                            if st.button("💾 保存", key=f"save_tt_ad_{mapping['id']}", use_container_width=True):
                                # 更新映射并获取受影响的日期
                                affected_dates = db.update_tt_ad_account_owner_mapping(mapping['ad_account_id'], new_owner)
                                if affected_dates is not None:
                                    st.info(f"🔄 正在重新聚合 {len(affected_dates)} 个日期的数据...")
                                    # 重新聚合受影响日期的数据
                                    if db.aggregate_owner_daily_for_dates(affected_dates):
                                        st.success(f"✅ 已更新: {mapping['ad_account_id']} -> {new_owner}，并重新聚合了 {len(affected_dates)} 个日期的数据")
                                    else:
                                        st.warning(f"⚠️ 映射已更新，但重新聚合失败，请手动运行聚合脚本")
                                    st.rerun()
                                else:
                                    st.error(f"❌ 更新失败: {mapping['ad_account_id']}")
            else:
                st.info("暂无TikTok广告账户映射数据")
    
    st.divider()

    start_date = st.session_state.start_date
    end_date = st.session_state.end_date

    # 排序选项
    sort_options = [
        ('gmv_desc', '销售额 ↓'),
        ('gmv_asc', '销售额 ↑'),
        ('spend_desc', '广告花费 ↓'),
        ('spend_asc', '广告花费 ↑'),
        ('roas_desc', 'ROAS ↓'),
        ('roas_asc', 'ROAS ↑'),
        ('owner_asc', '负责人 A→Z')
    ]
    selected_sort = st.selectbox(
        "排序方式",
        options=sort_options,
        index=0,
        format_func=lambda x: x[1]
    )

    sort_by_map = {
        'gmv': 'gmv',
        'spend': 'spend',
        'roas': 'roas',
        'owner': 'owner'
    }
    if selected_sort[0].startswith('gmv'):
        sort_by = 'gmv'
    elif selected_sort[0].startswith('spend'):
        sort_by = 'spend'
    elif selected_sort[0].startswith('roas'):
        sort_by = 'roas'
    else:
        sort_by = 'owner'
    sort_order = 'desc' if selected_sort[0].endswith('desc') else 'asc'

    data = db.get_owner_daily_summary(start_date, end_date, sort_by=sort_by_map.get(sort_by, 'owner'), sort_order=sort_order)
    if not data:
        st.info("📭 所选日期范围内暂无负责人数据")
        return

    df = pd.DataFrame(data)
    # 确保列存在
    for col in ['total_gmv', 'total_orders', 'total_visitors', 'avg_order_value', 'total_spend', 'tt_total_spend', 'total_spend_all', 'roas', 'conversion_rate']:
        if col not in df.columns:
            df[col] = 0.0

    # 格式化展示
    display_df = df.copy()
    display_df['销售额 (USD)'] = display_df['total_gmv'].apply(lambda x: f"${float(x):,.2f}")
    display_df['订单数'] = display_df['total_orders'].apply(lambda x: f"{int(x):,}")
    display_df['访客数'] = display_df['total_visitors'].apply(lambda x: f"{int(x):,}")
    display_df['客单价 (USD)'] = display_df['avg_order_value'].apply(lambda x: f"${float(x):,.2f}")
    display_df['Facebook广告花费 (USD)'] = display_df['total_spend'].apply(lambda x: f"${float(x):,.2f}")
    display_df['TikTok广告花费 (USD)'] = display_df['tt_total_spend'].apply(lambda x: f"${float(x):,.2f}")
    display_df['总广告花费 (USD)'] = display_df['total_spend_all'].apply(lambda x: f"${float(x):,.2f}")
    display_df['ROAS'] = display_df['roas'].apply(lambda x: "N/A" if pd.isna(x) else f"{float(x):.2f}")
    display_df['转化率'] = display_df['conversion_rate'].apply(lambda x: f"{float(x):.2f}%")
    
    # 创建自定义表格：负责人列是可点击的文字链接
    st.markdown("**💡 点击负责人名字查看该负责人的小时趋势图**")
    
    # 添加 CSS 样式，让按钮看起来像链接
    st.markdown("""
    <style>
    button[data-testid*="owner_click_"] {
        background-color: transparent !important;
        border: none !important;
        color: #0066cc !important;
        text-decoration: none !important;
        padding: 0.25rem 0 !important;
        font-weight: normal !important;
        text-align: left !important;
        box-shadow: none !important;
        width: 100% !important;
    }
    button[data-testid*="owner_click_"]:hover {
        text-decoration: underline !important;
        color: #0052a3 !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 表头
    header_cols = st.columns([2, 2, 1.5, 1.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5])
    headers = ['负责人', '销售额 (USD)', '订单数', '访客数', '客单价 (USD)', 'Facebook广告花费 (USD)', 'TikTok广告花费 (USD)', '总广告花费 (USD)', 'ROAS', '转化率']
    for i, header in enumerate(headers):
        with header_cols[i]:
            st.markdown(f"**{header}**")
    
    st.divider()
    
    # 表格行：负责人名字是可点击的按钮（样式为链接）
    for idx, row in display_df.iterrows():
        row_cols = st.columns([2, 2, 1.5, 1.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5])
        with row_cols[0]:
            owner_name = row['owner']
            # 使用按钮但样式为链接（透明背景，蓝色文字，无边框）
            if st.button(owner_name, key=f"owner_click_{idx}", use_container_width=True, 
                        help=f"点击查看 {owner_name} 的小时趋势图"):
                # 设置状态并触发 rerun
                st.session_state.owner_sel = owner_name
                st.rerun()
        with row_cols[1]:
            st.text(row['销售额 (USD)'])
        with row_cols[2]:
            st.text(row['订单数'])
        with row_cols[3]:
            st.text(row['访客数'])
        with row_cols[4]:
            st.text(row['客单价 (USD)'])
        with row_cols[5]:
            st.text(row['Facebook广告花费 (USD)'])
        with row_cols[6]:
            st.text(row['TikTok广告花费 (USD)'])
        with row_cols[7]:
            st.text(row['总广告花费 (USD)'])
        with row_cols[8]:
            st.text(row['ROAS'])
        with row_cols[9]:
            st.text(row['转化率'])
    
    # 弹窗触发逻辑（放在表格渲染后）
    if "owner_sel" in st.session_state and st.session_state.owner_sel:
        # 调用弹窗函数（传递 date 类型）
        show_owner_modal(
            st.session_state.owner_sel, 
            start_date, 
            end_date
        )
        
        # 弹窗关闭后，清除状态（防止下次 rerun 时自动弹出）
        st.session_state.owner_sel = None


def render_store_list_section():
    """渲染店铺列表区域"""
    from calendar import monthrange
    
    st.divider()  # 分隔线
    st.subheader("📊 各店铺数据汇总")
    
    # 日期选择区域
    st.markdown("**选择日期范围**")
    
    # 快捷选择按钮（第一行）
    quick_cols = st.columns(5)
    with quick_cols[0]:
        if st.button("今天", key='quick_today', use_container_width=True):
            today = beijing_time().date()
            st.session_state.store_list_date_start = today
            st.session_state.store_list_date_end = today
            st.rerun()
    
    with quick_cols[1]:
        if st.button("昨天", key='quick_yesterday', use_container_width=True):
            yesterday = beijing_time().date() - timedelta(days=1)
            st.session_state.store_list_date_start = yesterday
            st.session_state.store_list_date_end = yesterday
            st.rerun()
    
    with quick_cols[2]:
        if st.button("上周", key='quick_last_week', use_container_width=True):
            today = beijing_time().date()
            days_since_monday = (today.weekday()) % 7
            last_monday = today - timedelta(days=days_since_monday + 7)
            last_sunday = last_monday + timedelta(days=6)
            st.session_state.store_list_date_start = last_monday
            st.session_state.store_list_date_end = last_sunday
            st.rerun()
    
    with quick_cols[3]:
        if st.button("上个月", key='quick_last_month', use_container_width=True):
            today = beijing_time().date()
            if today.month == 1:
                last_month_start = date(today.year - 1, 12, 1)
                last_day = monthrange(today.year - 1, 12)[1]
                last_month_end = date(today.year - 1, 12, last_day)
            else:
                last_month_start = date(today.year, today.month - 1, 1)
                last_day = monthrange(today.year, today.month - 1)[1]
                last_month_end = date(today.year, today.month - 1, last_day)
            st.session_state.store_list_date_start = last_month_start
            st.session_state.store_list_date_end = last_month_end
            st.rerun()
    
    with quick_cols[4]:
        # 占位，保持布局平衡
        st.empty()
    
    # 自定义日期选择器和排序（第二行）
    date_cols = st.columns([1, 1, 1])
    with date_cols[0]:
        selected_start_date = st.date_input(
            "开始日期",
            value=st.session_state.store_list_date_start,
            key='custom_start_date',
            help="选择开始日期"
        )
    with date_cols[1]:
        selected_end_date = st.date_input(
            "结束日期",
            value=st.session_state.store_list_date_end,
            key='custom_end_date',
            help="选择结束日期"
        )
    with date_cols[2]:
        # 排序选择器
        sort_options = [
            ('store_name', 'asc', '按店铺名称排序'),  # 与侧边栏排序一致
            ('total_gmv', 'desc', '按销售额降序'),
            ('total_gmv', 'asc', '按销售额升序')
        ]
        # 找到当前选择的索引
        current_index = 0
        for idx, (sort_by, sort_order, _) in enumerate(sort_options):
            if sort_by == st.session_state.store_list_sort_by and sort_order == st.session_state.store_list_sort_order:
                current_index = idx
                break
        
        selected_sort = st.selectbox(
            "排序方式",
            options=sort_options,
            format_func=lambda x: x[2],
            index=current_index,
            key='store_list_sort'
        )
    
    # 同步session_state
    if selected_start_date != st.session_state.store_list_date_start:
        st.session_state.store_list_date_start = selected_start_date
        st.rerun()
    if selected_end_date != st.session_state.store_list_date_end:
        st.session_state.store_list_date_end = selected_end_date
        st.rerun()
    if selected_sort[0] != st.session_state.store_list_sort_by or selected_sort[1] != st.session_state.store_list_sort_order:
        st.session_state.store_list_sort_by = selected_sort[0]
        st.session_state.store_list_sort_order = selected_sort[1]
        st.rerun()
    
    # 验证日期范围
    if selected_start_date > selected_end_date:
        st.error("⚠️ 开始日期不能晚于结束日期，请重新选择")
        st.stop()
    
    # 查询数据
    stores_data = db.get_all_stores_summary(
        st.session_state.store_list_date_start,
        st.session_state.store_list_date_end
    )
    
    if not stores_data:
        st.info("📭 所选日期范围内暂无数据")
        st.stop()
    
    # 转换为DataFrame
    df_stores = pd.DataFrame(stores_data)
    
    # 如果店铺名称为空或提取失败，使用Python重新提取
    if 'store_name' in df_stores.columns and 'shop_domain' in df_stores.columns:
        def get_store_name(row):
            store_name = row.get('store_name', '')
            if pd.isna(store_name) or store_name == '':
                return db.get_store_display_name(row['shop_domain'])
            return store_name
        df_stores['store_name'] = df_stores.apply(get_store_name, axis=1)
    elif 'shop_domain' in df_stores.columns:
        # 如果store_name列不存在，从shop_domain提取
        df_stores['store_name'] = df_stores['shop_domain'].apply(
            lambda x: db.get_store_display_name(x)
        )
    
    # 应用排序
    if st.session_state.store_list_sort_by == 'store_name':
        df_stores = df_stores.sort_values('store_name', ascending=(st.session_state.store_list_sort_order == 'asc'))
    elif st.session_state.store_list_sort_by == 'total_gmv':
        df_stores = df_stores.sort_values('total_gmv', ascending=(st.session_state.store_list_sort_order == 'asc'))
    
    # 格式化显示数据
    display_df = df_stores.copy()
    display_df['销售额 (USD)'] = display_df['total_gmv'].apply(lambda x: f"${float(x):,.2f}")
    display_df['订单数'] = display_df['total_orders'].apply(lambda x: f"{int(x):,}")
    display_df['访客数'] = display_df['total_visitors'].apply(lambda x: f"{int(x):,}")
    display_df['客单价 (USD)'] = display_df['avg_order_value'].apply(
        lambda x: f"${float(x):,.2f}" if float(x) > 0 else "$0.00"
    )
    
    # 选择要显示的列
    display_columns = ['store_name', '销售额 (USD)', '订单数', '访客数', '客单价 (USD)']
    display_df_final = display_df[display_columns].copy()
    
    # 重命名列为中文
    display_df_final.columns = ['店铺名称', '销售额 (USD)', '订单数', '访客数', '客单价 (USD)']
    
    # 显示表格（只读，无交互功能）
    st.markdown(f"**共 {len(df_stores)} 个店铺**")
    st.dataframe(
        display_df_final,
        use_container_width=True,
        height=600  # 固定高度，支持滚动
    )


def main():
    """主函数"""
    # 启动时检查端口
    port = STREAMLIT_CONFIG.get('port', 8502)
    if is_port_in_use(port):
        logger.warning(f"端口 {port} 已被占用")
        available_port = find_available_port(port)
        if available_port:
            logger.warning(f"建议使用端口: {available_port}")
        # 注意：这里只记录警告，不阻止启动，因为Streamlit自己会处理端口冲突
    
    if not check_login():
        login_page()
    else:
        # 顶部导航栏
        col1, col2 = st.columns([6, 1])
        with col1:
            st.write(f"欢迎，{st.session_state.username} ({st.session_state.role})")
        with col2:
            if st.button("退出登录"):
                username = st.session_state.username  # 保存用户名
                st.session_state.logged_in = False
                st.session_state.username = None
                st.session_state.role = None
                clear_login_token(username)  # 清除保存的令牌（传入用户名）
                st.rerun()
        
        render_dashboard()


if __name__ == '__main__':
    main()

