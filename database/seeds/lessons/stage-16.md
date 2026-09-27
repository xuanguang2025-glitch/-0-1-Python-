# 阶段 16 · 机器学习基础

## ml-intro

### 理论

机器学习让程序从数据中学习规律而非硬编码规则。主要范式：监督学习（有标签，回归/分类）、无监督学习（无标签，聚类/降维）、强化学习（奖励驱动）。核心流程：数据 → 特征 → 训练 → 评估 → 预测。

### 代码

```python
# 概念示意：用「经验」预测（不是真训练，理解流程用）
def rule_based_predict(area: float, price_per_sqm: float = 8000.0) -> float:
    """最朴素的房价估计（规则法）。"""
    return area * price_per_sqm

print(rule_based_predict(100))   # 800000.0
# 机器学习会从 (面积, 价格) 样本中自动学出这个系数
```

### 示例

```python
# 监督 vs 无监督
# 监督：给「邮件 + 是否垃圾」样本 -> 学分类
# 无监督：只给「用户消费数据」-> 自动分群
```

### 练习

1. 列举三个生活中可用 ML 解决的场景并判断范式。
2. 说明特征、标签、样本三者的含义。

### 注意事项

- 数据质量 > 模型复杂度。
- 先建立基线（简单方法），再上模型。

### 常见错误

- 用测试数据调参（数据泄漏）。
- 过早上复杂模型，忽视数据。

## train-test-split

### 理论

为评估泛化能力，把数据分为训练集与测试集（常见 8:2 或 7:3）。训练集学参数，测试集评估。必要时再划出验证集做调参。划分要随机且分层（分类任务）。

### 代码

```python
from sklearn.model_selection import train_test_split
from sklearn.datasets import load_iris

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(X_train.shape, X_test.shape)
```

### 示例

```python
from sklearn.model_selection import train_test_split

# 三划分：训练/验证/测试
X_train, X_tmp, y_train, y_tmp = train_test_split(X, y, test_size=0.3, random_state=0)
X_val, X_test, y_val, y_test = train_test_split(X_tmp, y_tmp, test_size=0.5, random_state=0)
print(X_train.shape, X_val.shape, X_test.shape)
```

### 练习

1. 对 Iris 数据做 8:2 划分并检查标签分布。
2. 用 `stratify` 保持类别比例。

### 注意事项

- 设 `random_state` 保证可复现。
- 分类任务用分层划分。

### 常见错误

- 不划分，直接在训练集上评估（虚高）。
- 数据泄漏（预处理在划分前用全量统计）。

## sklearn-basics

### 理论

scikit-learn 提供统一 API：`fit`（训练）、`predict`（预测）、`transform`（转换）、`score`（评分）。`Pipeline` 把「预处理 + 模型」串起来，避免流程混乱与泄漏。

### 代码

```python
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = LogisticRegression(max_iter=200)
model.fit(X_train, y_train)
print(model.score(X_test, y_test))       # 准确率
print(model.predict(X_test[:3]))
```

### 示例

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("clf", LogisticRegression(max_iter=200)),
])
# pipeline.fit(X_train, y_train); pipeline.predict(X_test)
```

### 练习

1. 用 sklearn 训练一个分类器并报告准确率。
2. 用 `Pipeline` 组合标准化与模型。

### 注意事项

- 预处理放进 Pipeline，避免泄漏。
- 特征需为数值矩阵 `X`，标签为 `y`。

### 常见错误

- 未标准化导致某些模型（如 SVM）表现差。
- 直接对字符串标签训练（先编码）。

## linear-regression

### 理论

线性回归用一条直线（或超平面）拟合自变量与连续目标的关系，最小化残差平方和。评估用 MSE/RMSE/R²。适合预测价格、销量等连续值。

### 代码

```python
import numpy as np
from sklearn.linear_model import LinearRegression

X = np.array([[1], [2], [3], [4], [5]])       # 面积/特征
y = np.array([2.1, 3.9, 6.2, 7.8, 10.1])      # 目标

model = LinearRegression()
model.fit(X, y)
print(f"斜率={model.coef_[0]:.2f}, 截距={model.intercept_:.2f}")
print(f"预测 6 的房价: {model.predict([[6]])[0]:.2f}")
```

### 示例

```python
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

model = LinearRegression().fit(X, y)
pred = model.predict(X)
print("R²:", r2_score(y, pred))
print("RMSE:", mean_squared_error(y, pred) ** 0.5)
```

### 练习

1. 用线性回归拟合一组数据并画回归线。
2. 报告 R² 并解释含义。

### 注意事项

- 线性回归假设线性关系与特征独立。
- R² 越接近 1 拟合越好（但需防过拟合）。

### 常见错误

- 只用训练集评估，忽略泛化。
- 强非线性数据硬套线性模型。

## classification

### 理论

分类预测离散类别（如垃圾邮件、鸢尾花品种）。常用算法：逻辑回归、KNN、决策树、随机森林、SVM。评估看重准确率、精确率、召回率、F1。

### 代码

```python
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

X, y = load_iris(return_X_y=True)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

clf = RandomForestClassifier(n_estimators=100, random_state=0)
clf.fit(X_train, y_train)
print(classification_report(y_test, clf.predict(X_test)))
```

### 示例

```python
from sklearn.neighbors import KNeighborsClassifier

def train_knn(X_train, y_train, k: int = 5):
    """训练 KNN 分类器。"""
    model = KNeighborsClassifier(n_neighbors=k)
    model.fit(X_train, y_train)
    return model
```

### 练习

1. 训练一个分类器并输出混淆矩阵。
2. 对比两个分类算法的 F1 分数。

### 注意事项

- 类别不平衡时准确率会误导，看 F1。
- KNN 对特征尺度敏感，需标准化。

### 常见错误

- 只看准确率忽视召回率。
- 未处理类别不平衡。

## model-evaluation

### 理论

不同任务用不同指标。分类：准确率、精确率（Precision）、召回率（Recall）、F1、ROC-AUC；回归：MSE、RMSE、MAE、R²。理解指标权衡（精确率与召回率常此消彼长）。

### 代码

```python
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

y_true = [1, 0, 1, 1, 0, 1]
y_pred = [1, 0, 0, 1, 0, 1]

print("准确率:", accuracy_score(y_true, y_pred))
print("精确率:", precision_score(y_true, y_pred))
print("召回率:", recall_score(y_true, y_pred))
print("F1    :", f1_score(y_true, y_pred))
print(confusion_matrix(y_true, y_pred))
```

### 示例

```python
# 混淆矩阵四种结果：TP / FP / FN / TN
# 精确率 = TP / (TP + FP)  预测为正里真正为正的比例
# 召回率 = TP / (TP + FN)  真正为正里被找出的比例
```

### 练习

1. 对同一预测计算四个指标并解释差异。
2. 说明什么场景更看重召回率（如疾病筛查）。

### 注意事项

- 指标要结合业务目标选择。
- 交叉验证得到更稳健的评估。

### 常见错误

- 单一指标定论。
- 忽视基线与方差（小样本波动大）。

## overfitting

### 理论

过拟合：模型记住训练集噪声，训练表现好但测试差。欠拟合：模型太简单，两者都差。缓解：更多数据、正则化（L1/L2）、简化模型、交叉验证、早停、Dropout。

### 代码

```python
from sklearn.tree import DecisionTreeClassifier

# 深树容易过拟合
deep = DecisionTreeClassifier(max_depth=None, random_state=0)
shallow = DecisionTreeClassifier(max_depth=3, random_state=0)
# deep.fit(X_train, y_train)   -> 训练接近 1，测试偏低
# shallow.fit(X_train, y_train) -> 泛化更好
```

### 示例

```python
from sklearn.linear_model import Ridge   # L2 正则

def train_ridge(X_train, y_train, alpha: float = 1.0):
    """带 L2 正则的线性回归，抑制过拟合。"""
    model = Ridge(alpha=alpha)
    model.fit(X_train, y_train)
    return model
```

### 练习

1. 对比深树与浅树在训练/测试集的表现。
2. 调整 `alpha` 观察正则强度影响。

### 注意事项

- 始终对比训练与验证表现。
- 正则强度需调参。

### 常见错误

- 只看训练准确率下结论。
- 用测试集反复调参造成信息泄漏。

## feature-engineering

### 理论

特征工程质量常比换模型更有效：数值标准化、类别编码（One-Hot/标签编码）、缺失填充、派生特征（如日期拆成星期）、分箱、降维。目标是让特征更有信息量。

### 代码

```python
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler

df = pd.DataFrame({"city": ["北京", "上海", "北京"], "age": [25, 30, 35]})

# 类别编码
encoded = OneHotEncoder(sparse_output=False).fit_transform(df[["city"]])
print(encoded)

# 数值标准化
scaled = StandardScaler().fit_transform(df[["age"]])
print(scaled)
```

### 示例

```python
import pandas as pd

def add_date_features(series: pd.Series) -> pd.DataFrame:
    """把日期列拆成年/月/星期等特征。"""
    dt = pd.to_datetime(series)
    return pd.DataFrame({"year": dt.dt.year, "month": dt.dt.month, "weekday": dt.dt.weekday})
```

### 练习

1. 对类别特征做 One-Hot 编码。
2. 从日期派生「是否周末」特征。

### 注意事项

- 编码器只在训练集 `fit`，再 `transform` 测试集。
- 高基数类别慎用 One-Hot（维度爆炸）。

### 常见错误

- 全量数据 `fit` 编码器（数据泄漏）。
- 对有序类别用 One-Hot 丢失顺序信息。

## clustering

### 理论

聚类是无监督学习：把相似样本自动分组，无需标签。K-Means 最常见，需预设簇数 k；DBSCAN 可发现任意形状并识别噪声。评估用轮廓系数。

### 代码

```python
from sklearn.cluster import KMeans
from sklearn.datasets import make_blobs
from sklearn.metrics import silhouette_score

X, _ = make_blobs(n_samples=300, centers=3, random_state=0)
km = KMeans(n_clusters=3, n_init=10, random_state=0)
labels = km.fit_predict(X)
print("簇中心:", km.cluster_centers_.round(2))
print("轮廓系数:", round(silhouette_score(X, labels), 3))
```

### 示例

```python
from sklearn.cluster import KMeans

def best_k(X, k_range=range(2, 8)) -> int:
    """用肘部法（惯性下降拐点）粗选簇数。"""
    inertias = {k: KMeans(n_clusters=k, n_init=10, random_state=0).fit(X).inertia_ for k in k_range}
    return min(inertias, key=lambda k: inertias[k])
```

### 练习

1. 用 K-Means 对客户数据分群并可视化。
2. 用轮廓系数评估不同 k 的效果。

### 注意事项

- K-Means 对初始点与尺度敏感，需标准化并多初始化。
- 簇数需要业务解释，不只看指标。

### 常见错误

- 未标准化导致量纲大的特征主导距离。
- 盲目相信肘部法自动给出的 k。
