### 线索查询接口 (clue/query) 返回数据

| 字段 (Field) | 含义说明 |
| :--- | :--- |
| `clue_id` | 线索唯一标识符，用于后台查询和跟进 |
| `enc_telephone` | 加密的电话号码，需要通过解密接口才能获取真实号码 |
| `telephone` | 另一个可能存放加密电话号码的字段，用于兼容性 |
| `name` | 线索记录的名称，默认多为“未命名” |
| `create_time_detail` | 线索的详细创建时间（如 `2026-06-05 18:37:31`） |
| `modify_time` | 线索最后修改的时间 |
| `author_nickname` | 获取该线索的抖音账号昵称（如“弘道学历提升中心”） |
| `author_douyin_id` | 获取该线索的抖音号（如 `hongdao1994`） |
| `author_role` | 授权抖音号的身份角色（如“商家”） |
| `advertiser_id` | 广告主ID，用于追踪广告来源 |
| `advertiser_name` | 广告主名称 |
| `ad_type` | 广告类型 |
| `promotion_id` | 计划/广告组ID |
| `promotion_name` | 计划/广告组名称（如“稳定川渝18-40岁出价270_06_05_08:50:10”） |
| `product_id` | 商品ID |
| `product_name` | 商品名称（如“学历提升免费咨询”） |
| `product_type` | 商品类型 |
| `content_id` | 视频内容ID |
| `video_id` | 视频ID |
| `flow_entrance` | 流量入口来源，数字代表不同渠道（如`2`代表广告） |
| `flow_type` | 流量类型，数字代表不同流量属性（如`1`或`2`） |
| `leads_page` | 留资页类型，数字代表不同页面形式（如`2`或`3`） |
| `clue_type` | 线索类型 |
| `clue_intention` | 用户意向标签 |
| `convert_status` | 转化状态 |
| `allocation_status` | 分配状态 |
| `effective_state` | 有效性状态 |
| `is_private_clue` | 是否为私密线索（`0`表示否，`1`表示是） |
| `qcpx_ticket_info` | 留资信息 |
| `qcpx_ticket_status` | 留资状态 |
| `auto_city_name` | 自动识别的城市（如“内江”） |
| `auto_province_name` | 自动识别的省份（如“四川”） |
| `province_name` | 省份 |
| `city_name` | 城市 |
| `county_name` | 区/县 |
| `country_name` | 国家 |
| `tel_addr` | 电话归属地（如“四川_内江”） |
| `address` | 详细地址 |
| `remark` | 备注信息 |
| `ext_info` | 扩展信息，JSON格式，用于存放其他补充数据 |
| `staff_douyin_id` | 跟进员工的抖音号 |
| `staff_nickname` | 跟进员工的昵称 |
| `staff_commerce_nickname` | 跟进员工的商业昵称 |
| `clue_owner_name` | 线索归属人 |
| `follow_life_account_id` | 跟进的生活服务账号ID |
| `follow_life_account_name` | 跟进的生活服务账号名称（如“四川弘道经理学院”） |
| `follow_life_account_type` | 跟进的生活服务账号类型 |
| `follow_poi_id` | 跟进的门店POI ID |
| `intention_life_account_name` | 意向生活服务账号名称 |
| `intention_poi_id` | 意向门店POI ID |
| `root_life_account_id` | 根生活服务账号ID |
| `source_craftsman_douyin_id` | 来源手艺人抖音号 |
| `source_craftsman_nickname` | 来源手艺人昵称 |
| `component_event_type_tags` | 组件事件类型标签 |
| `system_tags` | 系统标签 |
| `tags` | 自定义标签 |
| `order_id` | 关联的订单ID |
| `order_status` | 关联的订单状态 |
| `tool_id` | 使用的工具ID |
| `title_id` | 标题ID |
| `image_id` | 关联的图片ID |
| `weixin` | 用户填写的微信号 |
| `age` | 用户年龄 |
| `gender` | 用户性别 |
| `business` | 商业信息 |
| `ad_id` | 广告创意ID |
| `action_type` | 动作类型 |
| `search_bid_word` | 搜索竞价词 |
| `follow_state_name` | 关注状态名称 |
| `req_id` | 请求ID |
| `remark_dict` | 备注字典 |
| `page` | 分页信息，包含`page_number`（当前页）、`page_size`（每页大小）、`page_total`（总页数）、`total`（总线索数） |
| `extra` | 扩展信息，包含错误码、描述等 |

这些字段里，`enc_telephone`、`create_time_detail`、`author_nickname`、`product_name` 这些应该都是你用得上的。有不清楚的字段可以随时再问我～