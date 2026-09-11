# 微网与外部电网电力调控策略

完成范围：问题一至问题四的模型与计算、预测误差和备用对照、独立核验、MATLAB黑白灰图件，以及包含模型评价、结论、参考文献和附录的完整LaTeX论文。

## 文件组织

- `data/raw/`：原题、附件一至四及原始结果模板的原样副本；`data/manifest.json` 记录来源和SHA-256。
- `code/`：Python求解、独立验证、Excel导出及MATLAB绘图源码。
- `results/`：五个题目要求的结果工作簿、未舍入的逐时段CSV、完整JSON、逐日检查点和敏感性结果。
- `verification/`：数值核验、来源对照、软件版本和排版检查。
- `paper/`：主文档、分章节LaTeX、自动生成表格、MATLAB图表及 `build/main.pdf`。

## 数据口径

采用144个十分钟区间，观测标签为区间结束时刻，功率除以6得到区间电量。充放电量与5000 kW上限均定义在微网侧，主模型两个单程效率均0.9，储电量范围1200至10800 kWh。问题一初末储电量6000 kWh；允许弃光但不售电。

`result1.xlsx`保留模板的两个工作表和行数，数值不预先舍入。CSV与JSON保存全部计算精度；论文显示四位小数，因此表中舍入后相加可能与总量末位略有差异。

## 复现

1. Python 3.12或兼容版本安装 `requirements.txt`（本机使用项目 `.deps` 中的求解依赖及Codex自带的读取库）。运行 `python code/solve_q1.py`，再运行 `python code/validate_q1.py`。
2. 在MATLAB R2024a或兼容版本中将 `code/` 加入路径，运行 `plot_q1`。输出矢量PDF、300 dpi PNG和可编辑FIG。图表全部由MATLAB绘制。
3. Excel导出使用Node.js与 `@oai/artifact-tool`，运行 `node code/export_xlsx.mjs`，从原模板和 `results/q1.json` 生成结果表。本机 `code/node_modules` 指向Codex运行时；其他机器需自行提供该依赖。
4. 进入 `paper/`，执行两次 `xelatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex`。需要XeLaTeX、中文字体和模板依赖宏包；本机使用MiKTeX，模板使用宋体、黑体和Times New Roman。

运行顺序为求解→独立验证→MATLAB绘图→Excel导出→LaTeX编译。正文和表格统一读取自动生成结果，修改输入或模型后应完整重跑。对不同等价最优解，个别时段可能不同，应优先比较可行性与目标值；不把某个求解器的逐时段选择视为唯一最优方案。

## 问题二的交付与复现

问题二以1月为学习期，从2月1日的6000 kWh起连续运行334天。每日计划锁定后不再修改，48小时远端目标为6000 kWh，实际午夜状态连续传递。日内每次调用仅取得当前测量；未来情景调度是前瞻松弛，实际账单按执行结果独立计算。

- `results/result2.xlsx`保留计划购电、充放电、紧急购电三个工作表。计划表最后一列为当日总费用，包含计划费与5倍电价的紧急费；分项见`q2_daily.csv`。紧急表逐日合并连续区间，无紧急购电的日期也保留。
- `results/q2_detail.csv`保存全部48096个十分钟区间的实际执行与费用；`q2_daily.csv`保存334天汇总。
- `results/q2_report.json`保存策略比较、指定日期及敏感性结果，是MATLAB图表与论文表格的共同来源。
- `results/q2/{main,deterministic,no_storage}/`保存每个策略的每日NPZ检查点及配置，包括预测、情景、概率、锁定计划、实际执行和求解状态。
- `verification/q2/`保存因果性、物理与费用核验以及内部数值重求解记录；这些调查说明不属于论文正文。

从本目录运行以下命令。HiGHS固定为1.15.1，随机种子固定，求解采用单线程；依赖已加入根目录`requirements.txt`。

```text
python code/solve_q2.py --variant main
python code/solve_q2.py --variant deterministic
python code/solve_q2.py --variant no_storage
python code/q2_perfect_information.py
python code/q2_sensitivity.py
python code/test_q2_controller.py
python code/audit_q2_artifacts.py
python code/report_q2.py
node code/export_q2_xlsx.mjs
python code/validate_q2_xlsx.py
```

`report_q2.py`先核验三个完整回测，再统一生成CSV、JSON和LaTeX表格。首次小规模计时可用`--end 33 --tag pilot`执行2月1日至2日，控制器测试也读取这两个检查点。正式运行按日原子保存，重复同一命令自动续算；参数、输入或求解代码哈希改变时必须用新的`--tag`。三组策略可独立并行运行，完整回测需数分钟至数十分钟，取决于硬件。

结果生成后在MATLAB运行`plot_q2`，保存全年图、策略比较图及四个指定日期图的PDF、FIG和PNG。重新编译`paper/main.tex`即可更新整篇论文。XLSX中的数值不预先舍入，显示格式不改变存储精度。`openpyxl`仅用于读取与独立核验，不用于生成工作簿。

主方案与单预测计划方案使用相同的多情景滚动控制器，无储能方案使用同样情景的80%净负荷分位数购电。完全信息下界使用全期实测数据并允许期末库存自由，不能解释为在线可执行方案。14情景、4800/7200 kWh末端目标的敏感性实验在四个指定日期使用相同历史和日初储电量，是单日对照，不代表全年替代策略。

求解器数值状态异常时先对原LP冷启动重求解；仍失败才执行可行储能规则并记录事件。正式汇总要求没有回退事件。历史数值重求解与等值检查点恢复的来历保留在内部验证记录中。不同策略的期末库存单独报告，辅助库存估值不修改实际账单。

## 问题三的交付与复现

问题三继续从2月1日6000 kWh开始，连续运行334天。主方案采用0、6、12、18点光伏预报，后面三个时刻允许调整当天尚未交付的购电量；原计划始终保留为0点基准。取消部分退回原购电费、支付50%违约费，新增部分按1.5倍电价购买，每段按最终交付量一次结算。另一种“原计划照付再加违约费”口径作为独立对照，不混入主结果。

`result3.xlsx`包含四张表：原计划、最终有效调整量、实际充放电及合并紧急购电区间。原计划表的费用是原计划金额；调整表的费用是最终总费用，含退款、违约费、增购费和紧急费。因此不能再把两张表的费用相加。

`results/q3_detail.csv`保存48096段实际执行和结算分项，`q3_daily.csv`保存每日汇总，`q3_versions.csv`保存四个发布时刻对当日剩余区间的购电版本和光伏预测。`results/q3_report.json`为论文表格与MATLAB的共同输入。每个策略每天的NPZ还保留完整48小时预测/情景、历史样本起点、概率权重、调整候选预计费用及求解状态。

复现命令如下：

```text
python code/solve_q3.py --end 33 --tag pilot
python code/test_q3.py
python code/run_q3_suite.py
python code/q3_sensitivity.py
python code/audit_q3_scenarios.py
python code/report_q3.py
node code/export_q3_xlsx.mjs
python code/validate_q3_xlsx.py
```

然后在MATLAB中运行`plot_q3`，进入`paper/`编译两次`main.tex`。所有图表仍使用MATLAB，保存矢量PDF、PNG和FIG。导出器依赖与字体要求同前。

全年实验默认最多8个单线程工作进程，运行10组策略：八种预报选用组合、全部预报仅调储能、全部预报采用另一种结算口径。也可逐个运行`solve_q3.py --variant main`等命令，策略名见该脚本中的`VARIANTS`。每个策略独立存储检查点并按日续算；不得对同一个策略同时启动两个进程。参数和输入源码哈希改变时使用新`--tag`。运行日志位于`verification/q3/`。

14情景及4800/7200 kWh末端目标的敏感性实验仅在四个指定日期按主方案同起点执行。预报生成严格遵循发布时刻，采用整点功率的分段线性积分；超出已发布24小时范围的远端预测采用最近完整一天光伏，仅作前瞻。结论不外推至附件没有提供的发布时间。

## 完整论文与黑白图件修订

当前稿已按问题重述、问题分析、统一假设与符号、数据处理、四问模型、综合检验、模型评价、结论及参考文献组织。聚类与权重更新、当前控制规则、数值重求解和详细敏感性表集中在附录。第四问加入历史价格预测、联合价格误差情景及实际交付价格结算。

仅重建论文图件和排版时，不必重算优化模型：在MATLAB中将 `code/` 加入路径，依次运行 `plot_overview; plot_q1; plot_q2; plot_q3; verify_bw_figures`，随后进入 `paper/` 用XeLaTeX编译两次。全部图件采用黑白灰、不同线型和稀疏空心标记；费用构成结合白底黑边、灰度填充及必要的纹理区分，不限于点线或斜线。纹理由 `bw_pattern_rect.m` 生成，图例与柱体使用相同方法。

早期前三问修订记录保存在 `verification/paper_revision/`。本轮之前的快照位于 `verification/before_q4/`，当前第四问核验位于 `verification/q4/`。旧的 `verify_paper_revision.py` 仅适用于当时的三问稿；当前四问稿以 `verify_q4_delivery.py` 为交付检查入口。


## 第四问与补充实验

第四问将未来价格视为未知。0点用最近7个完整历史日同一时段平均价预测当日和次日价格，价格中心预测日内不改。联合情景将同一历史起点的负载、光伏、价格误差配对，7个代表情景来自最近28个已完整观测的48小时样本。实际执行只能读取当前价格，最终按交付区间实际价格结算。

两套标准工作簿：`result4-2.xlsx`包含不调整购电的计划、储能和紧急购电三张表，计划表最后一列为含紧急费的最终总费用；`result4-3.xlsx`包含原计划、最终有效量、储能和紧急购电四张表，原计划表费用为原计划金额，调整表费用为最终总费用，不能相加。结果明细中的普通计划金额、退款、违约费、增购费和紧急费分别保存。

```text
python code/solve_q4.py --variant q2 --end 33 --tag pilot_q2
python code/solve_q4.py --variant main --end 33 --tag pilot_main
python code/test_q4.py
python code/run_q4_suite.py
python code/q4_perfect_information.py
python code/forecast_diagnostics.py
python code/reserve_compare.py
python code/q4_report.py
node code/q4_export.mjs
python code/validate_q4_workbooks.py
```

在MATLAB中运行 `plot_overview; q4_figures`，保留既有前三问图件。全量输出就绪后统一编译LaTeX。最后运行 `python code/verify_q4_delivery.py` 核验交付；本轮只作一轮最终排版检查，不反复微调页面。

`results/q4/`包含11个全年策略目录及各自配置、每日NPZ原子检查点；每个NPZ记录预测、联合情景、阶段权重、四次购电版本、实际价格和物理执行。`q4_report.json`是表格、图形和导出的共同来源。运行同一命令自动按日续算；修改输入或求解源码后应使用新tag，不覆盖旧配置。当前批处理在不同进程中运行11个独立策略，每个HiGHS求解器使用一个线程。

电价点预测对照保留联合场景选出的负载/PV轨迹及相同权重更新方式，只把各情景未来价格替换为中心预测，以分离价格误差轨迹进入目标函数的作用。两个主方案的既有固定电价调度还按附件四重新计费，报告价格变化与重新优化的不同贡献。

`forecast_diagnostics.py`的误差统一为实际减预测，电量单位为十分钟kWh；Q3使用与调度相同的线性插值积分，按相同目标区间比较新旧预报。`reserve_compare.py`在Q2/Q3四个指定日以原全年主方案的实际日初库存为起点，预留未来放电能力与区间末库存，当前执行时释放备用。正式对照在 `results/reserve_verified/`，不替代前三问全年主结果。

内部草稿及未采纳的探索输出集中于 `verification/q4/superseded_drafts/`，不是论文结果或复现入口。第一问替代效率计算仍仅保留作内部口径核查，不进入论文正文或附录。
