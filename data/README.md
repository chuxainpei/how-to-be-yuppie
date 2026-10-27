# 数据表说明

全部为 UTF-8、制表符分隔（TSV）、首行列名、不使用引号。由 `python3 tools/book.py merge` 从 `data/fragments/` 合并生成的表请改碎片文件，不要直接改合并结果。

| 文件 | 一行是什么 | 生成方式 |
|---|---|---|
| `topics.tsv` | 一个课题：ID、模块、标题、文件路径、必答问题、费用与不适范围、状态 | 手工维护 |
| `prices.tsv` | 一个价格样本 | 由 `fragments/*-prices.tsv` 合并 |
| `sources.tsv` | 一个来源 | 由 `fragments/*-sources.tsv` 合并 |
| `terms.tsv` | 一个术语 | 由 `fragments/*-terms.tsv` 合并 |
| `outlet-stores.tsv` | 某奥莱官方列表中的一个品牌 | 手工维护 |
| `dining-comparisons.tsv` | 同店同餐在某渠道的一次观察 | 手工维护 |
| `platform-observations.tsv` | 平台公开页面的一条观察（前期调研） | 手工维护 |

## prices.tsv

| 列 | 含义 |
|---|---|
| price_id | `P-<课题>-<序号>`，唯一 |
| topic_id | 所属课题 |
| city / institution | 城市；机构或渠道名称 |
| item | 项目或商品，含规格 |
| amount / currency / unit | 金额（可为区间文字）、币种、计价单位（每牙、单眼、每人、盒等） |
| includes / excludes | 包含与另收 |
| price_type | government_guide 政府指导价 / institution_posted 机构公示价 / promo 活动价 / list 官网或挂牌价 / menu 菜单价 / platform_listing 平台展示价 / individual_quote 个案报价 / wholesale_reference 采购或批发参考（不是零售价） |
| effective_date / accessed_date | 页面标注的生效或发布日期；本轮采集日期。二者不同义 |
| source_id | 对应 `sources.tsv` |
| notes | 口径说明与限制 |

## sources.tsv

| 列 | 含义 |
|---|---|
| source_id | `SRC-<模块字母>-<序号>`：D 牙齿、E 视力、S 皮肤、H 理发、F 健身、B 品牌、V 餐厅、C 省钱 |
| source_type | government_policy / institution_price / professional_guideline / hospital_education / merchant_rule / platform_rule / video / personal_experience / news / reference_repo / platform_listing（平台展示页） |
| verification_status | read_supported 本轮打开并读到支持内容（包括下载后逐页阅读的 PDF、用 curl 取回的页面，方法写在 notes 或 supports）/ located_only 仅定位或只见摘要 / restricted 登录、限流或超时 / conflict 冲突待核 |
| supports | 该来源支持的具体事实 |

来源类型不是医学证据等级；同一来源对不同事实可能有不同状态，细节见 `docs/核验记录/<ID>.md`。

## outlet-stores.tsv

`outlet	outlet_city	brand	category	editorial_positioning	official_listing_url	accessed_date	notes`。`editorial_positioning` 是本书的编辑分组，不是官方评级。

## dining-comparisons.tsv

`comparison_id	city	store	date_observed	party_size	dishes	channel	listed_price	conditions	total_out_of_pocket	evidence_url	verification_status	notes`。`unverified` 行不能用来证明最低价。
