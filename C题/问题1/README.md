# C题问题一工作区

## 目录

- `code/solve_q1.py`：读取附件、建立线性规划并生成全部结果。
- `data/`：完整逐时段计算明细。
- `result/result1.xlsx`：按官方模板生成的提交文件。
- `问题1.md`：可继续修改的论文初稿。

## 运行

在项目根目录执行：

```bash
C题/问题1/.venv/bin/python C题/问题1/code/solve_q1.py
```

依赖安装在 `问题1/.venv` 中，包括 NumPy、SciPy 和 openpyxl。

重新创建环境时可执行：

```bash
python3 -m venv C题/问题1/.venv
C题/问题1/.venv/bin/python -m pip install -r C题/问题1/requirements.txt
```
