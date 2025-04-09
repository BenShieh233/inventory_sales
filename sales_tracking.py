import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")
st.title("HD-Lowes平台SKU销量追踪")

st.sidebar.header("上传文件")
sales_file = st.sidebar.file_uploader("上传平台销量表文件", type=["xlsx", "xls"])

if sales_file is not None:
    # 读取数据，同时跳过前4行
    sales_df = pd.read_excel(sales_file, skiprows=4)
    
    # 确保订单日期为 datetime 格式，若存在转换异常则为空值
    if 'Order Date' in sales_df.columns:
        sales_df['Order Date'] = pd.to_datetime(sales_df['Order Date'], errors='coerce')
    
    # 计算销量: 假设销量= Unit Cost * Quantity
    sales_df['Sales Amount(销量)'] = sales_df['Unit Cost'] * sales_df['Quantity']
    
    st.write("数据预览", sales_df.head())
    
    #################################################
    # 1. 全局过滤: Merchant 和 时间范围过滤
    #################################################
    with st.expander("功能模块一：按平台聚合的历史订单销量数据"):
        st.sidebar.header("功能模块一：平台历史订单销量数据")
        
        # Merchant 多选过滤，默认全选
        merchant_list = sales_df['Merchant'].dropna().unique().tolist()

        selected_merchants = st.sidebar.multiselect("请选择销售平台", options=merchant_list, default=merchant_list)
    
        # 时间范围过滤（全局），注意用户未选中结束日期时不报错
        st.sidebar.subheader("时间范围过滤（总览）")
        # 采用订单日期中的最小和最大值作为默认值
        default_start = sales_df['Order Date'].min()
        default_end = sales_df['Order Date'].max()
    
        start_date = st.sidebar.date_input("开始日期", value=default_start)
        end_date = st.sidebar.date_input("结束日期", value=default_end)
        
        # 当用户选择了完整的时间范围时，过滤数据
        if start_date and end_date:
            # 时间过滤
            mask = (sales_df['Order Date'] >= pd.to_datetime(start_date)) & (sales_df['Order Date'] <= pd.to_datetime(end_date))
            filtered_df = sales_df.loc[mask]
            # Merchant 过滤
            filtered_df = filtered_df[filtered_df['Merchant'].isin(selected_merchants)]
            
            # ---------------------------
            # 计算所有平台总和
            overall_df = filtered_df.groupby('Order Date', as_index=False)['Sales Amount(销量)'].sum()
            overall_df['Merchant'] = '所有平台总和'
            
            # 计算各 Merchant 的销量
            merchant_df = filtered_df.groupby(['Order Date', 'Merchant'], as_index=False)['Sales Amount(销量)'].sum()
            
            # 合并数据
            combined_df = pd.concat([overall_df, merchant_df], ignore_index=True)
            
            # 填充缺失日期
            all_dates = pd.date_range(start=start_date, end=end_date, freq='D')
            all_merchants = combined_df['Merchant'].unique()
            complete_index = pd.MultiIndex.from_product([all_dates, all_merchants], names=['Order Date', 'Merchant'])
            combined_df = (combined_df
                        .set_index(['Order Date', 'Merchant'])
                        .reindex(complete_index, fill_value=0)
                        .reset_index())
            st.write("筛选数据预览", combined_df)

            # 绘制折线图：同时展示总销量及各平台销量
            fig = px.line(combined_df, x='Order Date', y='Sales Amount(销量)', color='Merchant', 
                        title="所有平台总和及各 Merchant 销量趋势", markers=True)

            # 添加数字标签
            fig.update_traces(text=combined_df['Sales Amount(销量)'], textposition='top center', hovertemplate = '日期: %{x} 销量: %{y}', showlegend=True)

            st.plotly_chart(fig, use_container_width=True)

            # ---------------------------
            # 绘制百分比饼图：统计各 Merchant 占所选时间范围内总销量的百分比
            # （此处不包括“所有平台总和”）
            pie_df = filtered_df.groupby('Merchant', as_index=False)['Sales Amount(销量)'].sum()
            
            # 创建饼图：显示每个平台所占比例，并以两位小数显示百分比
            fig_pie = px.pie(pie_df, names='Merchant', values='Sales Amount(销量)', 
                            title="各平台占总销量百分比")

            # 更新饼图 traces 设置：在内部显示百分比，悬停时显示百分比（后两位小数）
            fig_pie.update_traces(textposition='inside',
                                texttemplate='%{value} (%{percent:.2%})',
                                hovertemplate='销量: %{value}, 百分比: %{percent:.2%}<extra></extra>')
            
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("请选择完整的时间范围（包含起始日期和结束日期）")
    
    #################################################
    # 2. SKU销量排序模块
    #################################################
    with st.expander("功能模块二：SKU销量排序"):
        st.header("SKU销量排序")

        st.sidebar.subheader("功能模块二：Vendor SKU 销量排名筛选条件")
        # 按Vendor SKU和平台进行聚合
        sku_sales = filtered_df.groupby(['Vendor SKU', 'Merchant'], as_index=False)['Sales Amount(销量)'].sum()

        # 侧边栏筛选条件：指定销量的最小值和最大值
        min_sales = st.sidebar.number_input("最低销量", min_value=0.0, value=None, step=0.01, format="%.2f")
        max_sales = st.sidebar.number_input("最高销量", min_value=0.0, value=None, step=0.01, format="%.2f")

        # 如果设置了销量范围，则过滤数据
        if min_sales is not None or max_sales is not None:
            if min_sales is not None and max_sales is not None:
                sku_sales = sku_sales[(sku_sales['Sales Amount(销量)'] >= min_sales) & (sku_sales['Sales Amount(销量)'] <= max_sales)]
            elif min_sales is not None:
                sku_sales = sku_sales[sku_sales['Sales Amount(销量)'] >= min_sales]
            elif max_sales is not None:
                sku_sales = sku_sales[sku_sales['Sales Amount(销量)'] <= max_sales]
            
        sku_sales_sorted = sku_sales.sort_values(by='Sales Amount(销量)', ascending=False)

        # 如果没有符合条件的数据，显示提示信息
        if not sku_sales_sorted.empty:

            # 拉条筛选排名范围
            total_skus = len(sku_sales_sorted)

            # 检查 session_state 中是否已经有值，如果没有就初始化

            if 'n' not in st.session_state:
                st.session_state.n = 1  # 默认起始排名
            if 'm' not in st.session_state:
                st.session_state.m = st.session_state.n  # 默认结束排名与起始排名相同

            # 更新 n 和 m
            n = st.sidebar.number_input('起始排名n', min_value=1, max_value=total_skus, value=st.session_state.n)
            m = st.sidebar.number_input(f'结束排名m (上限为{total_skus})', min_value=n, max_value=total_skus, value=st.session_state.m)

            # 将输入值存入 session_state，以便保存状态
            st.session_state.n = n
            st.session_state.m = m
            if st.session_state.m > total_skus:
                m = total_skus
                st.session_state.m = m  # 更新 session_state 中的 m 值
            # 获取排名n-m的Vendor SKU
            selected_skus = sku_sales_sorted.iloc[n-1:m].reset_index(drop=True)
            
            # 显示选择的Vendor SKU
            st.write(f"显示销量排名 {n}-{m} 的Vendor SKU (日期与 <span style='color:blue;'>功能模块一</span> 中的 时间范围 一致)", unsafe_allow_html=True)
            st.dataframe(selected_skus)
            group_sort = st.sidebar.checkbox("按总销量排序 Vendor SKU（不分平台）", value=True)
            if group_sort:
                # 绘制条形图
                fig_bar = px.bar(
                    selected_skus,
                    x='Vendor SKU',
                    y='Sales Amount(销量)',
                    barmode='stack',
                    text='Sales Amount(销量)',
                    title=f"{start_date} ~ {end_date} 销量排名{n} - {m} SKU条形图",
                    category_orders={"Vendor SKU": selected_skus}  # ✅ 强制按这个顺序排序           
                )
                fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside',                            
                                    hovertemplate='Vendor SKU: %{x}<br>销量: %{y:.2f}<extra></extra>'  # 悬停时显示两位小数
                                    )
                fig_bar.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_title="Vendor SKU", yaxis_title="销量")

                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                
                fig_bar = px.bar(
                    selected_skus,
                    x='Vendor SKU',
                    y='Sales Amount(销量)',
                    color='Merchant',
                    barmode='stack',
                    text='Sales Amount(销量)',
                    title=f"{start_date} ~ {end_date} 销量排名{n} - {m} SKU条形图"
                )
                fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                fig_bar.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', xaxis_title="Vendor SKU", yaxis_title="销量")

                st.plotly_chart(fig_bar, use_container_width=True)
    
        else:
            st.warning("您选择的范围已超出当前数据集最大/最小值，请重新设置过滤条件")

    #################################################
    # 3. SKU查询模块
    #################################################
    with st.expander("功能模块三：SKU销量数据查询"):
        st.sidebar.header("功能模块三：SKU销量数据查询")
        
        # 列出所有的Vendor SKU供选择
        sku_list = sales_df['Vendor SKU'].dropna().unique().tolist()
        selected_sku = st.sidebar.selectbox("请选择需要查看的SKU", sku_list)
        
        # SKU查询专属时间范围过滤控件
        st.sidebar.subheader("SKU查询时间范围")
        sku_default_start = sales_df['Order Date'].min()
        sku_default_end = sales_df['Order Date'].max()
        sku_start_date = st.sidebar.date_input("SKU 开始日期", value=sku_default_start, key='sku_start')
        sku_end_date = st.sidebar.date_input("SKU 结束日期", value=sku_default_end, key='sku_end')
        
        # 筛选出选中的SKU数据
        sku_df = sales_df[sales_df['Vendor SKU'] == selected_sku]
        
        if sku_start_date and sku_end_date:
            mask_sku = (sku_df['Order Date'] >= pd.to_datetime(sku_start_date)) & (sku_df['Order Date'] <= pd.to_datetime(sku_end_date))
            sku_filtered_df = sku_df.loc[mask_sku]

            total_sales = sku_filtered_df['Sales Amount(销量)'].sum()
    
            # 显示 SKU 总销量
            st.write(f"在 {sku_start_date} 到 {sku_end_date} 期间，SKU {selected_sku} 的总销量为: {round(total_sales, 2)}")
    
            # 1) 按平台（Merchant）聚合：分别计算每个平台的销量
            sku_agg_platform = sku_filtered_df.groupby(['Order Date', 'Merchant'], as_index=False)['Sales Amount(销量)'].sum()
            
            # 填充缺失日期
            sku_all_dates = pd.date_range(start=sku_start_date, end=sku_end_date, freq='D')
            sku_agg_platform['Order Date'] = pd.to_datetime(sku_agg_platform['Order Date'])
            all_skus = sku_agg_platform['Merchant'].unique()
            
            # 生成完整的日期和Merchant的组合
            sku_combinations = pd.MultiIndex.from_product([sku_all_dates, all_skus], names=['Order Date', 'Merchant'])
            sku_agg_platform = sku_agg_platform.set_index(['Order Date', 'Merchant']).reindex(sku_combinations, fill_value=0).reset_index()
            
            # 绘制SKU在各平台的销量变化曲线
            fig_platform = px.line(sku_agg_platform, x='Order Date', y='Sales Amount(销量)', color='Merchant',
                                title=f"SKU {selected_sku} 各平台销量变化趋势", markers=True)
            # 添加数字标签
            fig_platform.update_traces(text=combined_df['Sales Amount(销量)'], textposition='top center', hovertemplate = '日期: %{x} 销量: %{y}', showlegend=True)
            st.plotly_chart(fig_platform, use_container_width=True)
            
            st.write(f"SKU {selected_sku} 在 {sku_start_date} 到 {sku_end_date} 期间的订单数据")
            st.dataframe(sku_filtered_df)
            
        else:
            st.info("请为SKU查询选择完整的时间范围（起始日期和结束日期）")
