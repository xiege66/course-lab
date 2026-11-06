# 交付验证记录

验证日期：2026-11-06。平台：Windows，MinGW g++，Python 3。源码基准为 GitHub 固定提交归档，四个目标文件的归一化 SHA256 存于 apply.py。

已执行且通过：

1. `g++ -std=c++17 -Wall -Wextra -Werror -Iinclude tests/policy_test.cpp`，随后执行程序输出 `policy tests passed`。覆盖 selectivity 边界、预算增长、有效数量不足、待完成 I/O、启发式退出与硬上限。
2. `python -m unittest discover -s tests -v`，设置固定源码 fixture，3 项测试全部通过。覆盖原始源码上 git apply 检查、实际应用、反向检查，四个源文件 SHA256，实验矩阵 15 个任务的参数和结果收集、禁止覆盖既有实验目录。
3. `python -m compileall -q`，所有交付 Python 文件语法检查通过。

实验矩阵检查使用模拟子进程输出，不产生真实 ANN 性能数据。未执行 Linux GateANN 完整编译和链接、真实 AIO 生命周期测试、YFCC Debug/Formal 检索或 Recall/延迟测量。当前机器没有可用 Linux 实验环境及原始索引。源码补丁检查成功不等于完整编译成功；正式提交前应在原 Ubuntu 实验机执行 README 中的构建、Debug 检查及 75 次 Formal 消融实验。

报告可新增如下实现说明，实际链接上传后填写：

> 已提供过滤感知预算与有效候选终止的 GateANN 实现，包括可选 FullAdj 邻居裁剪和原版关闭优化的对照路径。实现采用每查询独立状态，保持 SSD 索引格式兼容，并提供固定版本安装校验、策略测试和五组消融实验脚本。提前终止依赖 PQ 启发式，不能保证召回率；目前已完成独立策略与补丁兼容性验证，尚未完成真实工作负载上的效果测量。代码链接以实际发布的 GitHub 仓库及提交号为准。
