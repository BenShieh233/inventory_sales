import streamlit as st
import pandas as pd
import re
import plotly.express as px

st.title("库存和销量数据交互式分析")

##############################
# 1. 用户上传文件
##############################
st.sidebar.header("上传文件")
inventory_file = st.sidebar.file_uploader("上传库存表文件", type=["xlsx", "xls"])
sales_file = st.sidebar.file_uploader("上传平台销量表文件", type=["xlsx", "xls"])

##############################
# 定义各平台的字段映射和前缀规则
##############################
# 每个平台销量表中需要用户定义：SKU 字段名、日期字段名、销量字段名
# 注意：字段名称需要与你实际文件中一致
platform_mappings = {
    "HDCarroSales": {"sku": "Vendor SKU", "date": "Order Date", "sales": "Promotion Sales"},
    "HDCASales": {"sku": "Vendor SKU", "date": "Order Date", "sales": "Sales"},
    "HDTriSales": {"sku": "Vendor SKU", "date": "Order Date", "sales": "Sales"},
    "LSSales": {"sku": "Item Number", "date":"PO Date", "sales": "Promotion Total Amount"},
    "MSSales": {"sku": "Item Number", "date": "PO Date", "sales": "Total Amount"},
    "OSSales": {"sku": "Item Number", "date": "PO Date", "sales": "Total Amount"},
    "WFCarroSales": {"sku":"Item Number", "date":"PO Date", "sales": "Total Amount"},
    "WFTriSales": {"sku": "Item Number", "date":"PO Date", "sales": "Total Amount"},
    "WFSanSales": {"sku": "Item Number", "date": "PO Date", "sales": "Total Amount"},
    "WFQZSales": {"sku": "Item Number", "date": "PO Date", "sales": "Total Amount"},
    "LumensSales": {"sku": "Item Number", "date": "PO Date", "sales": "Total Amount"}
    # 可根据需要添加其他平台
}

# 定义各平台的 SKU 前缀规则
# 比如：库存表可能有平台前缀，如 H, N, HCA-等，平台销量表也可能有 V, W-, A- 等前缀
# 这里只是示例，实际请按需要修改
sales_prefixes = ["HCA-", "NTRI-", "HTRI-", "MS-", "O", "W-", "W", "H", "N", "L", "QZ-", "SL-", "TRI"]
inventory_prefixes = ["V", "W-", "A-", "AMZ-V"]

# 编译正则表达式，用于去除前缀（库存和销量可能不同，按需要分别处理）
inv_prefix_pattern = re.compile(rf"^({'|'.join(inventory_prefixes)})")
sales_prefix_pattern = re.compile(rf"^({'|'.join(sales_prefixes)})")

def extract_core_sku(sku, pattern):
    """去除 sku 中的前缀，返回核心 SKU（若不是字符串则返回空字符串）"""
    if isinstance(sku, str):
        return pattern.sub('', sku)
    return ''

##############################
# 2. 读取库存表文件，提取 sku_list
##############################
if inventory_file is not None:
    # 默认读取第一个 Sheet
    inv_df = pd.read_excel(inventory_file, sheet_name='单品超100台的吊扇明细')
    
    st.subheader("库存表数据预览")
    st.dataframe(inv_df)
    
    # 用户输入库存表中用于匹配的 SKU 字段名称
    inv_sku_field = st.text_input("请输入库存表中 SKU 字段名称", value="SKU")
    
    # 检查库存表中是否有该字段
    if inv_sku_field in inv_df.columns:
        # 生成库存 SKU 列（去掉库存表中前缀）
        inv_df["Core_SKU"] = inv_df[inv_sku_field].apply(lambda x: extract_core_sku(x, inv_prefix_pattern))
        # 提取库存表中的 SKU 列表（去重后）
        sku_list = inv_df["Core_SKU"].dropna().unique().tolist()
    else:
        st.error(f"库存表中没有找到字段：{inv_sku_field}")
        sku_list = []
else:
    sku_list = []

##############################
# 3. 读取平台销量表文件的 sheet name
##############################
if sales_file is not None:
    sales_xls = pd.ExcelFile(sales_file)
    sheet_names = sales_xls.sheet_names
    st.sidebar.write("平台销量表 Sheet 列表：", sheet_names)
    
    # 允许用户选择需要处理的平台（注意：这里默认平台映射中的 Sheet 名称与 Excel 中一致）
    selected_platforms = st.sidebar.multiselect("选择要处理的平台（Sheet 名称）", 
                                                options=sheet_names,
                                                default=[s for s in sheet_names if s in platform_mappings])
else:
    selected_platforms = []

##############################
# 4. 用户根据 sku_list 提供选项
##############################
if sku_list:
    selected_sku = st.selectbox("请选择需要查看的 SKU（库存表中的核心 SKU）", sku_list)
else:
    st.info("请先上传库存表文件以获取 SKU 列表")
    selected_sku = None

##############################
# 5. 根据选中的 SKU，从各平台销量数据中提取销量
##############################
if sales_file is not None and selected_platforms and selected_sku is not None:
    # 用于存放各平台处理后的销量数据
    platform_sales_data = []
    
    for platform in selected_platforms:
        try:
            # 读取当前平台数据
            df_platform = pd.read_excel(sales_file, sheet_name=platform)
            
            # 若该平台在映射中有预定义字段，使用预定义字段；否则让用户输入
            mapping = platform_mappings.get(platform, None)
            if mapping is None:
                st.warning(f"平台 {platform} 未定义字段映射，请手动指定。")
                sku_field = st.text_input(f"平台 {platform} 的 SKU 字段", value="SKU")
                date_field = st.text_input(f"平台 {platform} 的日期字段", value="Order Date")
                sales_field = st.text_input(f"平台 {platform} 的销量字段", value="Promotion Sales")
            else:
                sku_field = mapping["sku"]
                date_field = mapping["date"]
                sales_field = mapping["sales"]
            
            # 检查是否包含指定字段
            if sku_field not in df_platform.columns:
                st.error(f"平台 {platform} 中没有找到 SKU 字段: {sku_field}")
                continue
            if date_field not in df_platform.columns:
                st.error(f"平台 {platform} 中没有找到日期字段: {date_field}")
                continue
            if sales_field not in df_platform.columns:
                st.error(f"平台 {platform} 中没有找到销量字段: {sales_field}")
                continue
            
            # 处理前缀：提取核心 SKU（这里使用销量表的前缀规则，可按需要修改）
            df_platform["Core_SKU"] = df_platform[sku_field].apply(lambda x: extract_core_sku(x, sales_prefix_pattern))
            # 筛选出与选中的 SKU 核心部分匹配的数据
            platform_df = df_platform[df_platform["Core_SKU"] == selected_sku].copy()
            # 确保日期列为 datetime 类型
            platform_df[date_field] = pd.to_datetime(platform_df[date_field])
            
            # 添加平台标识
            platform_df["Platform"] = platform
            
            # 只保留需要的列
            platform_df = platform_df[[date_field, "Platform", sales_field]]
            platform_df.rename(columns={date_field:"Order Date", sales_field:"Sales"}, inplace=True)
            
            platform_sales_data.append(platform_df)
        except Exception as e:
            st.error(f"读取平台 {platform} 数据出错：{e}")
    
    if platform_sales_data:
        # 合并所有平台的数据
        all_platform_sales = pd.concat(platform_sales_data)
        
        ##############################
        # 6. 聚合日期，计算总销售额和各平台销售额随时间变动的曲线
        ##############################
        # 总销售额
        total_sales = all_platform_sales.groupby("Order Date")["Sales"].sum().reset_index()
        # 各平台销售额
        platform_sales = all_platform_sales.groupby(["Order Date", "Platform"])["Sales"].sum().reset_index()
        
        ##############################
        # 7. 可视化库存量和总销售额
        ##############################
        st.subheader("总销售额变化趋势")
        fig_total = px.line(total_sales, x="Order Date", y="Sales",
                            title=f"SKU {selected_sku} 总销售额趋势",
                            markers=True)
        st.plotly_chart(fig_total)
        
        st.subheader("各平台销售额变化趋势")
        fig_platform = px.line(platform_sales, x="Order Date", y="Sales", color="Platform",
                               title=f"SKU {selected_sku} 各平台销售额趋势",
                               markers=True)
        st.plotly_chart(fig_platform)
    else:
        st.info("未从任何平台数据中提取到该 SKU 的销量。")
else:
    st.info("请上传销量表文件并选择至少一个平台以及一个 SKU。")

##############################
# 可选：可视化库存量
##############################
if inventory_file is not None and selected_sku is not None:
    # 假设库存表中有库存量字段，例如 "Inventory"
    inv_quantity_field = st.text_input("请输入库存表中库存量字段名称", value="Standard_QoH")
    if inv_quantity_field in inv_df.columns:
        inv_selected = inv_df[inv_df["Core_SKU"] == selected_sku]
        st.subheader("库存情况")
        st.dataframe(inv_selected[[inv_sku_field, inv_quantity_field]])
    else:
        st.info(f"库存表中不存在库存量字段 {inv_quantity_field}。")
