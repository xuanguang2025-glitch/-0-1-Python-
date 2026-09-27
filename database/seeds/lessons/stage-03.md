# 阶段 3 · 数据结构

## string-basics

### 理论

字符串是**不可变**的字符序列，支持索引 `s[0]`、负索引 `s[-1]` 与切片 `s[start:stop:step]`。任何「修改」都会生成新字符串，因此大量拼接要改用 `join`。

### 代码

```python
s = "PYTHON LAB"
print(s[0], s[-1])        # P B
print(s[0:6])             # PYTHON
print(s[:6], s[7:])       # PYTHON LAB
print(s[::-1])            # BAL NOHTYP
print(len(s))             # 10
print("LAB" in s)         # True
```

### 示例

```python
text = "  2026-09-26  "
clean = text.strip()
year, month, day = clean.split("-")
print(f"{year} 年 {month} 月 {day} 日")   # 2026 年 09 月 26 日
print(clean[5:10])                        # 09-26
```

### 练习

1. 把 `"python"` 变成 `"Python"` 与 `"PYTHON"`。
2. 判断一个字符串是否为回文（用切片）。
3. 从身份证号字符串中截取出生年月日。

### 注意事项

- 切片越界不会报错，只会截到边界。
- 字符串不可变，`s[0] = 'p'` 会报错，需构造新字符串。
- 频繁 `+=` 拼接长字符串效率低，用列表收集后 `"".join()`。

### 常见错误

- `IndexError: string index out of range` → 索引超长。
- `TypeError: 'str' object does not support item assignment` → 试图修改字符串。
- 中文字符按「字符」计数而非字节，做字节长度要用 `len(s.encode())`。

## string-methods

### 理论

常用方法：`split`（切分）、`join`（拼接）、`strip`（去空白）、`replace`（替换）、`find`/`index`（查找）、`startswith`/`endswith`（前缀判断）、`upper`/`lower`（大小写）。注意它们**返回新字符串**，不改原对象。

### 代码

```python
s = "  Python, Java, Go  "
print(s.strip())                     # Python, Java, Go
print(s.strip().split(", "))         # ['Python', 'Java', 'Go']
print("-".join(["a", "b", "c"]))     # a-b-c
print("hello".replace("l", "L"))     # heLLo
print("file.txt".endswith(".txt"))   # True
print("a,b,c".split(",", maxsplit=1))  # ['a', 'b,c']
```

### 示例

```python
raw = "  NAME :  小徐 ; AGE : 25  "
fields = {}
for part in raw.split(";"):
    if ":" in part:
        key, value = part.split(":", 1)
        fields[key.strip().lower()] = value.strip()
print(fields)   # {'name': '小徐', 'age': '25'}
```

### 练习

1. 把一句话按空格切分并统计单词数。
2. 清洗用户输入：去掉首尾空白、转小写、把多个空格压成一个。
3. 把 `"2026/09/26"` 转成 `"2026-09-26"` 并拆分。

### 注意事项

- `find` 找不到返回 `-1`，`index` 找不到抛 `ValueError`。
- `split()` 不带参数按任意空白切分并去掉空串，带 `","` 则严格按分隔符。
- 链式调用注意每一步的返回类型，`split` 返回列表，后面不能再 `.strip()`。

### 常见错误

- `AttributeError: 'list' object has no attribute 'strip'` → 顺序写反了。
- `ValueError: not enough values to unpack` → `split` 结果数量与解包变量不匹配。
- 用 `strip` 去掉了不该去的字符（默认会去掉所有空白，不止空格）。

## f-string

### 理论

f-string 在字符串前加 `f`，用 `{}` 嵌入表达式，是当前最推荐的格式化方式。支持格式说明符：`.2f`（两位小数）、`:>10`（右对齐宽 10）、`:,`（千分位）、`%`（百分比）以及 `=`（调试输出表达式与值）。

### 代码

```python
name, score = "小徐", 92.567
print(f"{name} 得分 {score:.2f}")            # 小徐 得分 92.57
print(f"|{name:>6}|{name:<6}|{name:^6}|")     # |   小徐|小徐   |  小徐  |
print(f"{1234567:,}")                        # 1,234,567
print(f"{0.856:.1%}")                        # 85.6%
print(f"{score=}")                           # score=92.567
```

### 示例

```python
items = [("咖啡", 32.5, 2), ("蛋糕", 18.0, 1)]
total = 0.0
for title, price, count in items:
    subtotal = price * count
    total += subtotal
    print(f"{title:<4} 单价 {price:>7.2f} × {count} = {subtotal:>8.2f}")
print(f"{'合计':<4} {'':>7}{' ' * 3}    {total:>8.2f}")
# 咖啡   单价   32.50 × 2 =    65.00
# 蛋糕   单价   18.00 × 1 =    18.00
# 合计                     83.00
```

### 练习

1. 输出一张对齐的小票（商品、单价、数量、小计右对齐）。
2. 用百分比格式输出正确率。
3. 用 `=` 语法打印变量名与值以调试。

### 注意事项

- `{}` 内可写任意表达式，但不要塞太复杂逻辑，影响可读性。
- 格式化说明符中英文标点不要混用，冒号必须是半角。
- Python 3.6+ 才支持 f-string，低版本需用 `str.format`。

### 常见错误

- `SyntaxError: f-string: expecting '}'` → 括号未闭合。
- `ValueError: Unknown format code 'd' for object of type 'float'` → 浮点用了整数格式。
- 字符串本意是字面花括号却没转义，需写 `{{` 和 `}}`。

## list-basics

### 理论

列表是**可变有序序列**，可存放任意类型（包括混合类型）。支持索引、切片、`in` 判断、`len`、遍历与排序。切片返回**新列表**，是浅拷贝。

### 代码

```python
nums = [3, 1, 4, 1, 5]
print(nums[0], nums[-1])      # 3 5
print(nums[1:4])              # [1, 4, 1]
print(sorted(nums))           # [1, 1, 3, 4, 5]
nums[0] = 10
print(nums)                   # [10, 1, 4, 1, 5]
print(nums + [9])             # 拼接返回新列表
```

### 示例

```python
scores = [88, 92, 79, 95, 60]
print(f"最高 {max(scores)} 最低 {min(scores)} 平均 {sum(scores) / len(scores):.1f}")
passed = [s for s in scores if s >= 80]
print(f"优秀人数 {len(passed)}：{passed}")
# 最高 95 最低 60 平均 82.8
# 优秀人数 3：[88, 92, 95]
```

### 练习

1. 输入一行数字，输出最大值、最小值与平均值。
2. 把列表中所有负数替换为 0。
3. 判断列表是否已经升序排列。

### 注意事项

- `b = a` 只是别名，改 `b` 会影响 `a`；要复制用 `a[:]` 或 `list(a)`。
- 浅拷贝对嵌套列表无效，深层复制用 `copy.deepcopy`。
- 列表可存不同类型，但混存类型会让后续逻辑更难维护。

### 常见错误

- `IndexError: list index out of range` → 索引超范围。
- 误以为 `b = a` 是复制，导致意外互相影响。
- 在遍历时删除元素造成漏项。

## list-methods

### 理论

增：`append`（尾部加单个）、`extend`（合并可迭代对象）、`insert`（指定位置插入）。删：`remove`（按值）、`pop`（按索引，返回元素）、`clear`。查：`index`、`count`。排：`sort`（原地）、`reverse`（原地）。

### 代码

```python
nums = [3, 1, 4]
nums.append(1)
nums.extend([5, 9])
nums.insert(0, 0)
print(nums)                     # [0, 3, 1, 4, 1, 5, 9]
nums.remove(1)                  # 删除第一个 1
last = nums.pop()               # 9
print(nums, last, nums.count(0))  # [0, 3, 4, 1, 5] 9 1
nums.sort(reverse=True)
print(nums)                     # [5, 4, 3, 1, 0]
```

### 示例

```python
records = [("数学", 92), ("语文", 88), ("英语", 95)]
records.sort(key=lambda item: item[1], reverse=True)
print([name for name, _ in records])   # ['英语', '数学', '语文']
```

### 练习

1. 维护一个待办列表：添加、完成（删除）、查看。
2. 按分数从高到低排序一组学生记录。
3. 统计列表中重复元素及其出现次数。

### 注意事项

- `sort` 原地修改且返回 `None`，`sorted` 返回新列表。
- `append` 与 `extend` 别混：`append([1,2])` 会让最后一个元素变成列表。
- `remove` 找不到值会抛 `ValueError`，先判断或用 `try`。

### 常见错误

- `x = lst.sort()` → `x` 是 `None`。
- `ValueError: list.remove(x): x not in list` → 值不存在。
- `pop` 空列表抛 `IndexError: pop from empty list`。

## tuple

### 理论

元组是不可变序列，常用作「固定结构的数据」与函数多返回值。因为不可变，元组可作字典键、可放入集合。解包（unpacking）是最实用的特性。

### 代码

```python
point = (3, 4)
x, y = point
print(x, y)              # 3 4

def min_max(nums: list[int]) -> tuple[int, int]:
    """返回列表的最小值与最大值。"""
    return min(nums), max(nums)

low, high = min_max([5, 2, 9])
print(low, high)         # 2 9

single = (1,)            # 单元素元组必须带逗号
print(type(single))      # <class 'tuple'>
```

### 示例

```python
students = [("小徐", 92), ("小林", 88)]
for name, score in students:
    print(f"{name}: {score}")

# 用星号收集剩余元素
first, *rest = [1, 2, 3, 4]
print(first, rest)      # 1 [2, 3, 4]
```

### 练习

1. 写一个函数同时返回商与余数，并在调用处解包。
2. 用元组作字典键记录棋盘坐标上的棋子。
3. 用 `*` 解包合并两个列表为元组。

### 注意事项

- 元组不可变指的是「元素引用不可变」，元素若是列表仍可被修改。
- 单元素元组要写 `(1,)`。
- 需要频繁增删应使用列表。

### 常见错误

- `single = (1)` 得到的是整数而不是元组。
- `TypeError: 'tuple' object does not support item assignment` → 试图修改元组。
- 解包数量不匹配 → `ValueError: too many values to unpack`。

## dict-basics

### 理论

字典是键值映射，键必须**可哈希**（不可变类型），值任意。查找平均是 O(1)。推荐用 `get` 或 `in` 判断存在性，而不是捕获 `KeyError`。

### 代码

```python
user = {"name": "小徐", "age": 25, "city": "上海"}
print(user["name"])                  # 小徐
print(user.get("email"))             # None
print(user.get("email", "未填写"))    # 未填写
print("age" in user)                 # True
user["age"] = 26                     # 更新
print(len(user))                     # 4
```

### 示例

```python
text = "banana"
counter: dict[str, int] = {}
for ch in text:
    counter[ch] = counter.get(ch, 0) + 1
print(counter)   # {'b': 1, 'a': 3, 'n': 2}
```

### 练习

1. 统计一段文本中每个单词出现的次数。
2. 合并两个字典，冲突时以第二个为准。
3. 反转字典的键值（值唯一时）。

### 注意事项

- 直接 `d[key]` 不存在时抛 `KeyError`，不确定时用 `get`。
- 字典保持插入顺序（Python 3.7+）。
- 列表不能当键（不可哈希），元组可以。

### 常见错误

- `KeyError: 'xxx'` → 键不存在。
- `TypeError: unhashable type: 'list'` → 用列表当键。
- 遍历时修改字典 → `RuntimeError`。

## dict-methods

### 理论

`keys/values/items` 返回视图，`update` 批量合并，`setdefault` 取不到时赋默认值，`pop` 弹出并删除，`popitem` 弹出最后一项，`fromkeys` 批量建键。

### 代码

```python
d = {"a": 1, "b": 2}
print(list(d.keys()), list(d.values()))     # ['a', 'b'] [1, 2]
d.update({"c": 3})
d.setdefault("d", []).append("x")
print(d)                                    # {'a': 1, 'b': 2, 'c': 3, 'd': ['x']}
print(d.pop("c"), "c" in d)                 # 3 False
```

### 示例

```python
# 分组：按首字母归类单词
words = ["apple", "banana", "avocado", "blueberry"]
groups: dict[str, list[str]] = {}
for word in words:
    groups.setdefault(word[0], []).append(word)
print(groups)
# {'a': ['apple', 'avocado'], 'b': ['banana', 'blueberry']}
```

### 练习

1. 把一个字典按值的大小分成「高分 / 低分」两组。
2. 合并多个字典，统计同名键出现次数。
3. 用 `items()` 输出排序后的键值对。

### 注意事项

- 视图是动态的，遍历期间不要改字典。
- `setdefault` 每次都会构造默认值（即使是列表字面量），可读但略有开销。
- `pop` 不存在的键要提供默认值，否则 `KeyError`。

### 常见错误

- 在 `for k in d.keys()` 中删除键 → 运行时错误。
- `d.items()` 解包顺序写反导致键值颠倒。
- 对视图排序：`sorted(d.keys())` 可以，直接 `d.keys().sort()` 不行。

## set-basics

### 理论

集合是无序、元素唯一、可哈希的容器。最大价值是**去重**与**O(1) 成员判断**。空集合必须用 `set()`，`{}` 是空字典。

### 代码

```python
nums = [1, 2, 2, 3, 3, 3]
unique = set(nums)
print(unique)              # {1, 2, 3}
print(len(unique))         # 3
print(2 in unique)         # True

letters = set("hello")
print(sorted(letters))     # ['e', 'h', 'l', 'o']
print(set())               # set()
```

### 示例

```python
# 找出两个列表中重复的元素
follows = {"小明", "小红", "小刚"}
fans = {"小红", "小美"}
print(follows & fans)      # {'小红'}
print(follows | fans)      # 五人并集
print(follows - fans)      # {'小明', '小刚'}
```

### 练习

1. 用集合去掉列表中重复的单词并保持可比较输出。
2. 判断两个列表是否有交集。
3. 统计一段文本中出现的不同字符数。

### 注意事项

- 集合无序，不要依赖遍历顺序；需要顺序时排序后输出。
- 集合元素必须可哈希，不能放列表、字典。
- 去重会丢失原顺序，若顺序重要可用 `dict.fromkeys()`。

### 常见错误

- `{}` 被当成空集合 → 实际是空字典。
- `TypeError: unhashable type: 'list'` → 放入不可哈希对象。
- 误用 `+` 合并集合 → 应用 `|` 或 `union`。

## set-operations

### 理论

集合运算：并集 `|`、交集 `&`、差集 `-`、对称差 `^`。对应方法 `union/intersection/difference/symmetric_difference` 可选任意可迭代对象。子集判断用 `<=`，真子集用 `<`。

### 代码

```python
a = {1, 2, 3, 4}
b = {3, 4, 5}
print(a | b)       # {1, 2, 3, 4, 5}
print(a & b)       # {3, 4}
print(a - b)       # {1, 2}
print(a ^ b)       # {1, 2, 5}
print({1, 2} <= a) # True
```

### 示例

```python
# 找出「已学但没掌握」的知识点
learned = {"列表", "字典", "推导式", "装饰器"}
mastered = {"列表", "字典"}
print(f"待复习：{sorted(learned - mastered)}")
# 待复习：['推导式', '装饰器']
```

### 练习

1. 找出两个班级的公共学生与独有学生。
2. 用集合运算判断两个列表是否包含相同元素（忽略顺序）。
3. 模拟权限系统：用户权限集合与所需权限集合的差集为空才放行。

### 注意事项

- 运算符会构造新集合，`update`/`intersection_update` 等是原地修改。
- 集合与 `frozenset` 区别：后者不可变，可作字典键。
- 大量集合运算时注意元素必须可哈希。

### 常见错误

- 把 `&` 当成「与运算」用于集合逻辑判断，语义与布尔运算不同。
- 用 `-` 求差集时方向搞反，导致结果为空。
- 期望结果有序，但集合无序导致输出不稳定。
