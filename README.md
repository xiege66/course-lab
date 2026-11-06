# GateANN 过滤感知预算与有效候选终止优化

本项目实现实验报告第 5.5 节的优化方向：针对强过滤条件下固定候选池产生的有效候选不足，在 GateANN 的预 I/O 过滤和 FullAdj 隧道展开阶段加入过滤感知预算、有效候选终止启发式，以及可选邻居裁剪。原 SSD 图格式与预构建索引保持兼容。

这是可应用到真实 GateANN 检索循环的 C++ 源码补丁，并附独立策略头文件、测试、五组消融实验和结果汇总脚本。当前交付没有真实数据上的优化性能结论；原报告中 L=320/5120 的结果是基线，不能写成新代码的测量结果。

## 对应版本与文件

- 课程仓库：https://gitee.com/wei-fangyu/fvs-course-lab ，核对版本 `e44eab5d1b040ffdebc80374a13b304a9c4d37de`。
- GateANN：https://github.com/GyuyeongKim/GateANN-public ，固定提交 `71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd`。该地址目前可能重定向到 NemoANN，仍以提交号为准。
- `include/adaptive_filter_policy.h`：原创建模及每查询预算状态，无 ANN 依赖。
- `patches/gateann_adaptive.patch`：修改检索循环、标签统计、统计结构和 YFCC 测试入口。
- `apply.py`：检查固定提交、四个目标文件哈希、补丁兼容性；支持重复执行，不执行 reset/checkout。
- `run_experiments.py`：复用课程原 adapter，随机化对照顺序，独立目录保存日志、命令、结果和参数。
- `summarize.py`：生成各组各桶的中位数、范围和 Recall 门槛检查。

## 实现与边界

1. 加载 Spmat 元数据时按标签统计不同节点数。单标签 selectivity 为精确比例；多标签合取取边际比例的最小值，仅作为上界估计，不假定标签独立。统计只使用 base 元数据，不读取 ground truth。
2. `selectivity` 模式将每查询候选池设为 `clamp(ceil(max(target,K)/s), minL, maxL)`，仍使用原图搜索的自然终止。
3. `adaptive` 模式从开始保留 `maxL` 大小的候选池，防止先前丢弃候选无法在预算增长后恢复。`initial/final` 是探索预算检查点，池容量始终为 maxL；到达检查点时按局部通过率向上调预算，最多到 maxL。检查点不强制终止，实际提前终止取决于下述启发式，节点扩展始终受 maxL 硬上限约束。
4. 只有精确距离完成的通过过滤节点才计为有效结果。达到目标有效数量且最佳未发 I/O 的 PQ frontier 距离超过第 K 个精确距离乘 margin，且没有待完成 I/O/待处理池内结果时，可提前终止；退出后先排空异步 I/O、释放锁并合并池内已读结果，再归还查询缓冲区。硬上限退出可能少于 K，结果槽使用 UINT32_MAX，避免缺失结果被误算为 ID 0。
5. 可选 `tunnel_keep=16` 将失败节点的未访问邻居按“精确标签通过优先、PQ 距离次之、ID 打破平局”排序，保留前 16 个。未保留的邻居不标 visited，可从其他路径恢复。默认 32 对课程 FullAdj=32 不裁剪。PQ 仍需计算全部邻居，该策略减少候选插入和后续展开，不保证减少本轮 PQ 计算；排序与额外过滤检查也可能使性能变差。

PQ 距离不是精确距离的严格下界，局部通过率也存在图遍历偏差。有效数量达到 32 不等于 Recall 达到 90%。因此提前终止和邻居裁剪均为待验证启发式，存在召回损失风险；必须用真实 workload 验证，未达标的组应如实判失败。所有可变状态为每查询私有，标签统计为加载后只读；不引入跨查询历史训练，避免线程调度影响预算。

## 安装与构建（原 Ubuntu 实验机）

将本目录放到课程仓库外或仓库中均可。假设课程仓库为 `/root/fvs-course-lab`，本代码为 `/root/fvs-gateann-optimization`：

```bash
cd /root/fvs-course-lab
# 已有系统源码和索引可复用；首次准备按课程 README 安装依赖
bash scripts/prepare_gateann.sh
python3 /root/fvs-gateann-optimization/apply.py --repo systems/GateANN-public
cmake -S systems/GateANN-public -B systems/GateANN-public/build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=17 -DUSE_AIO=ON
cmake --build systems/GateANN-public/build --target search_disk_index_yfcc -j 8
```

应先用课程脚本应用 AIO 兼容性补丁，再安装本补丁。之后无需再次运行 prepare 脚本；直接 cmake 编译。若版本或目标文件有本地改动，安装器会拒绝修改，请在单独的固定版本源码中安装。不要把本补丁应用到 PipeANN。

## 测试

```bash
cd /root/fvs-gateann-optimization
mkdir -p build
g++ -std=c++17 -Wall -Wextra -Werror -Iinclude tests/policy_test.cpp -o build/policy_test
./build/policy_test
python3 -m unittest discover -s tests -v
# 可选：对固定提交的未修改源码副本测试补丁应用和反向校验
FVS_SOURCE_FIXTURE=/path/to/pristine-gateann python3 -m unittest discover -s tests -v
```

交付前在 Windows MinGW g++ 上通过策略编译与执行、Python 语法检查及固定版本源码补丁应用/反向检查。**尚未完成 Linux GateANN 全量编译、AIO 运行或真实 YFCC Recall/性能测试**。独立策略测试不替代集成测试。

## 运行原版对照

不设 `FVS_OPT_MODE` 或设为 `off`，原检索分支保持原行为（新增的标签计数仍有初始化/内存代价，结果缺失槽修正始终启用）。严格测量未经修改原版的初始化/RSS，应另保留一套未打补丁的可执行文件。本包的两个 fixed 组是同一打补丁二进制关闭优化策略的对照。

```bash
cd /root/fvs-course-lab
FVS_OPT_MODE=off python3 adapters/gateann_adapter.py search \
  --repo systems/GateANN-public --dataset-root datasets/yfcc_course_v1 \
  --tier formal --run-root course_runs --bucket low --L 320 \
  --threads 1 --beamwidth 8 --k 10 --full-adj-neighbors 32 --cache-budget 0 \
  --run-id baseline-check
```

## 五组消融实验

先完成 Debug 数据的构建与正确性检查，核对 mode=off 输出与原始版本一致，再执行 Formal。实验参数为 K=10、threads=1、beamwidth=8、FullAdj=32、cache-budget=0；每桶每组默认 5 轮，共 75 次进程。五组分别为 fixed320、fixed5120、selectivity、adaptive（不裁剪）、adaptive_prune（保留 16 个邻居）。

```bash
python3 /root/fvs-gateann-optimization/run_experiments.py \
  --course-repo /root/fvs-course-lab \
  --repo /root/fvs-course-lab/systems/GateANN-public \
  --dataset-root /root/fvs-course-lab/datasets/yfcc_course_v1 \
  --index-prefix /root/fvs-course-lab/course_runs/indices/gateann/formal_1000000/yfcc \
  --output /root/fvs-optimization-runs/experiment-01 --repeats 5
python3 /root/fvs-gateann-optimization/summarize.py \
  /root/fvs-optimization-runs/experiment-01/optimization_results.csv
```

输出目录必须不存在。脚本用 Linux 目录符号链接复用索引，不复制大索引；所有新结果写入独立目录，不污染正式实验。可用 `--dry-run` 仅预览命令（仍需存在数据集 tier 目录）。每个进程显式设置完整策略参数；失败立即停止并保留已完成记录，不静默跳过。

`manifest.json` 保存参数、顺序及环境变量；`command.json/run.log/results.csv` 由原 adapter 生成。查询输出保留原八列指标以兼容 adapter，另外在 `run.log` 的 `FVS_OPT L=...` 行输出平均初始/最终预算、扩展数、有效结果数、增长次数、提前终止/触顶比例和裁剪数。selectivity 模式的 expanded 为 0，因其使用原版自然终止，不启用扩展计数。

建议在每桶 Recall 全轮不低于 90% 的前提下，再比较 Low 的延迟与 tunnel_time 中位数是否低于同次测量 fixed5120，并报告所有失败组；对 High/Medium 检查是否退化。随机顺序控制部分机器波动，OS 页缓存并未强制冷却，请记录实际缓存策略、机器环境和重复范围。QPS 倒数口径沿用课程 adapter，内部逻辑 I/O 不能写成设备物理 I/O。参数调优应使用独立验证查询，不能在测试集上选参数后声称无偏收益。

## 参数

| 环境变量 | 默认值 | 作用 |
|---|---|---|
| FVS_OPT_MODE | off | off / selectivity / adaptive |
| FVS_OPT_MIN_L | 320 | 初始预算下限 |
| FVS_OPT_MAX_L | 5120 | 池容量和自适应扩展硬上限 |
| FVS_OPT_TARGET | 32 | 目标精确有效候选数，至少 K |
| FVS_OPT_PQ_MARGIN | 1.25 | 提前终止启发式距离系数 |
| FVS_OPT_TUNNEL_KEEP | 32 | 失败节点保留的邻居数量 |

整型参数范围为 1..1000000，minL 不得超过 maxL，K 不得超过 maxL。环境在每个进程启动时读取，运行中不改变。

## GitHub 交付

本次按要求仅交付代码，未创建远程仓库，不能填入虚构 GitHub 链接。新建 GitHub 空仓库后，在本目录执行（先替换示例地址）：

```bash
git init
git add .
git commit -m "Implement filter-aware GateANN search optimization"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/fvs-gateann-optimization.git
git push -u origin main
```

报告中的代码链接填写实际上传成功的仓库 URL，最好再附 commit permalink。本包仅包含新增代码及必要修改补丁，不包含课程数据、索引、实验原始记录或第三方完整源码。上游代码的使用和分发遵循上游许可；本包不替上游重新授予许可。
