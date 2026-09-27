# 阶段 15 · 数据分析

## numpy-basics

### 理论

NumPy 提供高效多维数组 `ndarray` 与向量化运算，是科学计算与数据分析的基础。相比 Python 列表，运算快得多且支持广播、切片、聚合。

### 代码

```python
import numpy as np

arr = np.array([1, 2, 3, 4, 5])
print(arr.shape, arr.dtype)        # (5,) int64
print(arr.sum(), arr.mean(), arr.max())

# 二维数组
matrix = np.array([[1, 2], [3, 4]])
print(matrix.shape)                # (2, 2)
```

### 示例

```python
import numpy as np

def normalize(values: list[float]) -> np.ndarray:
    """把数据归一化到 0-1。"""
    arr = np.array(values, dtype=float)
    return (arr - arr.min()) / (arr.max() - arr.min())

print(normalize([10, 20, 30, 40]))
```

### 练习

1. 创建一维与二维数组并打印形状/类型。
2. 用向量化计算数组的均值与标准差。

### 注意事项

- 优先向量化，避免 `for` 循环遍历数组。
- 注意 `dtype`，整数除法与浮点不同。

### 常见错误

- 混用 Python 列表与 NumPy 数组，性能下降。
- 对空数组求 `max()`，抛异常。

## numpy-array-ops

### 理论

数组运算支持逐元素加乘、布尔索引、切片（视图）、聚合（沿轴 `axis`）。理解「视图 vs 副本」很关键：切片是视图，修改会影响原数组。

### 代码

```python
import numpy as np

a = np.array([1, 2, 3, 4])
b = np.array([10, 20, 30, 40])

print(a + b)             # [11 22 33 44]
print(a * 2)             # [2 4 6 8]
print(a[a > 2])          # [3 4]（布尔索引）

m = np.array([[1, 2, 3], [4, 5, 6]])
print(m.sum(axis=0))     # 按列求和 [5 7 9]
print(m.sum(axis=1))     # 按行求和 [6 15]
```

### 示例

```python
import numpy as np

def moving_average(values: list[float], window: int = 3) -> np.ndarray:
    """简单滑动平均。"""
    arr = np.array(values, dtype=float)
    return np.convolve(arr, np.ones(window) / window, mode="valid")
```

### 练习

1. 用布尔索引筛选大于平均值的元素。
2. 沿不同轴做聚合并解释结果。

### 注意事项

- 切片是视图，需要独立数组用 `.copy()`。
- `axis=0` 沿行方向（对列聚合），含义要弄清。

### 常见错误

- 修改切片意外改到原数组。
- 混淆 `axis` 含义。

## numpy-broadcast

### 理论

广播（broadcasting）让不同形状的数组按规则对齐运算：从右往左比较维度，相等或其中一方为 1 即可广播。省去显式复制，提升表达力与性能。

### 代码

```python
import numpy as np

a = np.array([[1], [2], [3]])        # 形状 (3, 1)
b = np.array([10, 20])               # 形状 (2,)
print(a + b)
# [[11 21]
#  [12 22]
#  [13 23]]
```

### 示例

```python
import numpy as np

def standardize(matrix: list[list[float]]) -> np.ndarray:
    """按列标准化（每列减均值除标准差），演示广播。"""
    arr = np.array(matrix, dtype=float)
    mean = arr.mean(axis=0)          # 形状 (n_cols,)
    std = arr.std(axis=0)
    return (arr - mean) / std
```

### 练习

1. 用广播给矩阵每行加不同偏置。
2. 计算两两距离矩阵（广播技巧）。

### 注意事项

- 形状不兼容会抛 `ValueError`。
- 广播有时会隐式生成大数组，注意内存。

### 常见错误

- 维度对齐错误，运算报错。
- 误以为广播会复制数据（其实按需计算）。

## pandas-series

### 理论

pandas `Series` 是带标签的一维数组，可理解为「索引 + 值」。适合时间序列与单列数据，支持对齐、`apply`、缺失值处理。

### 代码

```python
import pandas as pd

s = pd.Series([10, 20, 30], index=["a", "b", "c"], name="scores")
print(s["b"])            # 20
print(s.mean())          # 20.0
print(s[s > 15])         # b 20, c 30
print(s.isna().sum())    # 0
```

### 示例

```python
import pandas as pd

def fill_missing(s: pd.Series, value: float = 0.0) -> pd.Series:
    """填充缺失值。"""
    return s.fillna(value)
```

### 练习

1. 创建 Series 并用标签索引取值。
2. 用布尔条件筛选并做聚合。

### 注意事项

- Series 运算按索引对齐，注意标签一致性。
- `NaN` 参与运算需显式处理。

### 常见错误

- 用位置下标访问标签索引，语义混淆（用 `.iloc`/`.loc`）。
- 忽略 `NaN` 导致统计偏差。

## pandas-dataframe

### 理论

`DataFrame` 是二维表格（行索引 + 列），类似 Excel/数据库表。支持选择列、过滤行、新增列、排序、`groupby`、`merge`。是数据分析的主力结构。

### 代码

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["张三", "李四", "王五"],
    "age": [25, 30, 35],
    "score": [88, 92, 79],
})
print(df["name"])                       # 选列
print(df[df["score"] > 80])             # 过滤行
df["passed"] = df["score"] >= 60        # 新增列
print(df.sort_values("score", ascending=False).head(2))
```

### 示例

```python
import pandas as pd

def load_csv(path: str, **kwargs) -> pd.DataFrame:
    """读取 CSV。"""
    return pd.read_csv(path, encoding="utf-8", **kwargs)
```

### 练习

1. 从字典创建 DataFrame 并按列排序。
2. 筛选满足多条件的行并统计。

### 注意事项

- 链式赋值可能产生 `SettingWithCopyWarning`，用 `.loc` 赋值。
- `inplace` 参数建议显式赋值而非 inplace。

### 常见错误

- 就地修改切片数据未反映到原表。
- 列名含空格导致点号访问失败。

## data-cleaning

### 理论

真实数据常有缺失、重复、类型错误、异常值。清洗步骤：统一格式 → 处理缺失（删/填）→ 去重 → 类型转换 → 异常值处理。清洗质量直接决定分析结论可靠性。

### 代码

```python
import pandas as pd

df = pd.DataFrame({
    "name": ["张三", "李四", "张三", None],
    "age": ["25", "30", "25", "40"],
    "score": [88, None, 88, 950],
})

df["age"] = pd.to_numeric(df["age"], errors="coerce")
df["score"] = pd.to_numeric(df["score"], errors="coerce")
df = df.dropna(subset=["name"])              # 删除关键列缺失
df["score"] = df["score"].fillna(df["score"].median())   # 中位数填充
df = df.drop_duplicates(subset=["name"])     # 去重
df = df[df["score"] <= 100]                  # 去除异常值
print(df)
```

### 示例

```python
import pandas as pd

def clean_amount(series: pd.Series) -> pd.Series:
    """清理形如 '¥1,234.5' 的金额字符串。"""
    return (
        series.astype(str)
        .str.replace("¥", "", regex=False)
        .str.replace(",", "", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
```

### 练习

1. 清理一份含缺失与重复的表格。
2. 转换「日期字符串」列为 datetime 类型。

### 注意事项

- 删除数据前评估影响，优先填充。
- 转换失败用 `errors="coerce"` 转为 `NaN`。

### 常见错误

- 直接 `dropna()` 丢掉大量样本。
- 类型转换失败静默变 `NaN` 未检查。

## groupby-aggregate

### 理论

`groupby` 按某列分组后聚合（`sum`/`mean`/`count` 等），`agg` 可一次算多个指标，`transform` 返回与原表等长的结果，`pivot_table` 做透视。

### 代码

```python
import pandas as pd

df = pd.DataFrame({
    "dept": ["技术", "技术", "市场", "市场"],
    "name": ["A", "B", "C", "D"],
    "salary": [20000, 25000, 15000, 18000],
})

print(df.groupby("dept")["salary"].mean())
print(df.groupby("dept").agg(total=("salary", "sum"), avg=("salary", "mean"), n=("name", "count")))
```

### 示例

```python
import pandas as pd

def top_n_by_group(df: pd.DataFrame, group: str, value: str, n: int = 1) -> pd.DataFrame:
    """每组取 value 最大的前 n 行。"""
    return df.sort_values(value, ascending=False).groupby(group).head(n)
```

### 练习

1. 按部门统计人数与平均薪资。
2. 用 `transform` 给每行加上组内均值列。

### 注意事项

- 聚合前先清洗分组列（空值会被丢弃）。
- `groupby` 默认排序，可 `sort=False` 提速。

### 常见错误

- 分组列含 `NaN`，对应行被静默丢弃。
- `agg` 语法写错导致返回意外结构。

## matplotlib-basics

### 理论

Matplotlib 是基础绘图库。常用：`plot` 折线、`scatter` 散点、`bar` 柱状、`hist` 直方图。设置标题、轴标签、图例、中文与保存。

### 代码

```python
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei"]   # 中文
plt.rcParams["axes.unicode_minus"] = False

x = [1, 2, 3, 4]
y = [10, 20, 25, 30]

plt.plot(x, y, marker="o", label="销售额")
plt.title("月度销售额")
plt.xlabel("月份"); plt.ylabel("金额")
plt.legend()
plt.savefig("chart.png", dpi=120)
plt.close()
```

### 示例

```python
import matplotlib.pyplot as plt

def bar_chart(labels: list[str], values: list[float], title: str) -> None:
    """绘制柱状图并保存。"""
    plt.figure(figsize=(6, 4))
    plt.bar(labels, values)
    plt.title(title)
    plt.tight_layout()
    plt.savefig("bar.png", dpi=120)
    plt.close()
```

### 练习

1. 绘制一条折线图并加标题与图例。
2. 用直方图展示一组数据的分布。

### 注意事项

- 无 GUI 环境用 `Agg` 后端（`matplotlib.use("Agg")`）。
- 中文标题需配置字体，否则乱码。

### 常见错误

- 忘记 `plt.close()`，多次绘图内存累积。
- 中文显示为方框。

## data-visualization

### 理论

可视化的目标是「让数据说话」：选对图表类型（趋势用折线、比较用柱状、分布用直方图、关系用散点、占比用饼图），突出重点，避免误导（截断轴、双轴滥用）。

### 代码

```python
import matplotlib.pyplot as plt

def plot_trend(dates: list[str], values: list[float]) -> None:
    """趋势折线图最佳实践。"""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(dates, values, color="#2b6cb0", linewidth=2)
    ax.set_title("用户增长趋势")
    ax.grid(True, alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig("trend.png", dpi=120)
    plt.close(fig)
```

### 示例

```python
# 选图指南：
# 时间趋势 -> 折线   类别比较 -> 条形
# 分布     -> 直方图  两变量关系 -> 散点
# 占比     -> 饼/堆叠（类别≤5）
```

### 练习

1. 为同一数据集选择两种合适图表并说明理由。
2. 给图表加上数据标签。

### 注意事项

- 轴不截断（柱状图从 0 开始），避免夸大差异。
- 颜色语义一致，少用花哨配色。

### 常见错误

- 饼图类别过多难以辨认。
- 双 Y 轴制造误导性关联。
