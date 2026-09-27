# 阶段 10 · 数据结构与算法

## complexity-analysis

### 理论

复杂度描述算法耗时/耗空间随输入规模 n 的增长趋势，用大 O 表示。常见从快到慢：O(1) < O(log n) < O(n) < O(n log n) < O(n²) < O(2ⁿ)。分析时关注最高阶项并忽略常数。

### 代码

```python
def find_max(nums: list[int]) -> int:
    """一次遍历求最大值：时间 O(n)，空间 O(1)。"""
    best = nums[0]
    for n in nums:
        if n > best:
            best = n
    return best

def all_pairs(nums: list[int]) -> list[tuple[int, int]]:
    """所有两两组合：时间 O(n²)。"""
    return [(a, b) for a in nums for b in nums]
```

### 示例

```python
# O(1) 与 O(n) 对比
def get_first(nums: list[int]) -> int:
    return nums[0]                      # O(1)

def has_duplicates(nums: list[int]) -> bool:
    seen = set()                        # O(n) 时间，O(n) 空间
    for n in nums:
        if n in seen:
            return True
        seen.add(n)
    return False
```

### 练习

1. 分析冒泡排序与二分查找的复杂度。
2. 判断 `list` 的 `in` 与 `set` 的 `in` 复杂度差异并验证。

### 注意事项

- 关注最坏情况，也要了解平均情况。
- 空间换时间是常见优化。

### 常见错误

- 只看代码行数，忽略循环嵌套。
- 忘记 `list.append` 均摊 O(1)，但 `insert(0)` 是 O(n)。

## linear-search

### 理论

线性查找逐个比较，直到找到或遍历完。适用于无序数据，时间 O(n)。实现简单，是无序场景的基线方案。

### 代码

```python
def linear_search(nums: list[int], target: int) -> int:
    """返回目标下标，未找到返回 -1。"""
    for index, value in enumerate(nums):
        if value == target:
            return index
    return -1

print(linear_search([4, 2, 7, 1], 7))   # 2
print(linear_search([4, 2, 7, 1], 9))   # -1
```

### 示例

```python
def find_all(nums: list[int], target: int) -> list[int]:
    """返回所有匹配下标。"""
    return [i for i, v in enumerate(nums) if v == target]

print(find_all([1, 2, 1, 3, 1], 1))   # [0, 2, 4]
```

### 练习

1. 实现带提前返回的线性查找并统计比较次数。
2. 在对象列表中按某字段线性查找。

### 注意事项

- 数据有序时优先二分查找。
- 需要「所有匹配」时用列表推导式。

### 常见错误

- 找到后忘记 `return`，继续遍历。
- 混淆「下标」与「值」。

## binary-search

### 理论

二分查找要求**有序**数组。每次比较中间元素，将搜索区间减半，时间 O(log n)。关键在于边界处理（`left <= right`）与中点更新（防溢出）。

### 代码

```python
def binary_search(nums: list[int], target: int) -> int:
    """在升序数组查找目标下标，未找到返回 -1。"""
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        if nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

print(binary_search([1, 3, 5, 7, 9], 7))   # 3
```

### 示例

```python
def lower_bound(nums: list[int], target: int) -> int:
    """返回第一个 >= target 的下标（插入位置）。"""
    left, right = 0, len(nums)
    while left < right:
        mid = (left + right) // 2
        if nums[mid] < target:
            left = mid + 1
        else:
            right = mid
    return left
```

### 练习

1. 用二分查找求目标第一次出现的位置。
2. 在旋转有序数组中查找目标。

### 注意事项

- 数据必须先排序。
- 边界条件（`<=` 还是 `<`）要与区间定义一致。

### 常见错误

- `left`/`right` 更新写成 `mid` 导致死循环。
- 对无序数组用二分查找，结果错误。

## bubble-sort

### 理论

冒泡排序反复比较相邻元素并交换，每轮把最大值「冒」到末尾。时间 O(n²)，空间 O(1)。稳定但效率低，适合教学入门的排序算法。

### 代码

```python
def bubble_sort(nums: list[int]) -> list[int]:
    """原地冒泡排序（返回同一列表）。"""
    arr = nums[:]
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:          # 已有序，提前结束
            break
    return arr

print(bubble_sort([5, 2, 9, 1]))   # [1, 2, 5, 9]
```

### 示例

```python
def bubble_sort_desc(nums: list[int]) -> list[int]:
    """降序冒泡。"""
    arr = nums[:]
    for i in range(len(arr) - 1):
        for j in range(len(arr) - 1 - i):
            if arr[j] < arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
```

### 练习

1. 统计冒泡排序的交换次数。
2. 改写为对字符串按长度排序。

### 注意事项

- 加 `swapped` 标志可在最好情况（已有序）降到 O(n)。
- Python 交换用元组解包，无需临时变量。

### 常见错误

- 内层循环边界写错导致越界。
- 忘记 `arr = nums[:]`，意外修改了原列表。

## quick-sort

### 理论

快速排序选一个基准（pivot），把小于/大于它的元素分到两侧，再递归排序。平均时间 O(n log n)，最坏 O(n²)（已排序且选端点为基准）。原地排序、不稳定。

### 代码

```python
def quick_sort(nums: list[int]) -> list[int]:
    """快速排序（返回新列表，易读版）。"""
    if len(nums) <= 1:
        return nums[:]
    pivot = nums[len(nums) // 2]
    less = [n for n in nums if n < pivot]
    equal = [n for n in nums if n == pivot]
    greater = [n for n in nums if n > pivot]
    return quick_sort(less) + equal + quick_sort(greater)

print(quick_sort([3, 6, 1, 8, 2]))   # [1, 2, 3, 6, 8]
```

### 示例

```python
import random

def quick_sort_inplace(nums: list[int], lo: int = 0, hi: int | None = None) -> None:
    """原地快速排序（三路分区，随机基准）。"""
    if hi is None:
        hi = len(nums) - 1
    if lo >= hi:
        return
    pivot = nums[random.randint(lo, hi)]
    i, j, k = lo, lo, hi
    while j <= k:
        if nums[j] < pivot:
            nums[i], nums[j] = nums[j], nums[i]
            i += 1
            j += 1
        elif nums[j] > pivot:
            nums[j], nums[k] = nums[k], nums[j]
            k -= 1
        else:
            j += 1
    quick_sort_inplace(nums, lo, i - 1)
    quick_sort_inplace(nums, k + 1, hi)
```

### 练习

1. 用 Lomuto 分区实现原地快排。
2. 对比随机基准与固定基准在有序数据上的表现。

### 注意事项

- 随机基准可缓解最坏情况。
- 递归深度大时可改用迭代或 `sys.setrecursionlimit`。

### 常见错误

- 分区边界写错导致死递归。
- 未处理大量重复元素，退化为 O(n²)。

## merge-sort

### 理论

归并排序把数组一分为二，递归排序后合并两个有序子数组。时间稳定 O(n log n)，空间 O(n)，**稳定**排序。适合链表与需要稳定性的场景。

### 代码

```python
def merge_sort(nums: list[int]) -> list[int]:
    """归并排序。"""
    if len(nums) <= 1:
        return nums[:]
    mid = len(nums) // 2
    left = merge_sort(nums[:mid])
    right = merge_sort(nums[mid:])
    return _merge(left, right)

def _merge(a: list[int], b: list[int]) -> list[int]:
    """合并两个有序列表。"""
    result: list[int] = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            result.append(a[i]); i += 1
        else:
            result.append(b[j]); j += 1
    result.extend(a[i:])
    result.extend(b[j:])
    return result

print(merge_sort([5, 1, 4, 2, 8]))   # [1, 2, 4, 5, 8]
```

### 示例

```python
# 归并思想也可用于合并两个有序文件/流
def merge_two_sorted(a: list[int], b: list[int]) -> list[int]:
    return _merge(a, b)

print(merge_two_sorted([1, 3, 5], [2, 4, 6]))
```

### 练习

1. 实现自底向上的迭代归并排序。
2. 用归并排序统计逆序对数量。

### 注意事项

- `a[i] <= b[j]` 用 `<=` 保证稳定性。
- 空间开销 O(n)，大数据需权衡。

### 常见错误

- 合并时漏掉剩余元素。
- 递归切分点与合并区间不一致。

## stack-queue

### 理论

栈（Stack）先进后出（LIFO），队列（Queue）先进先出（FIFO）。Python 用 `list` 实现栈（`append`/`pop`），用 `collections.deque` 实现队列（`append`/`popleft`，O(1)）。

### 代码

```python
from collections import deque

# 栈
stack: list[int] = []
stack.append(1); stack.append(2)
print(stack.pop())          # 2（后进先出）

# 队列
queue: deque[int] = deque()
queue.append(1); queue.append(2)
print(queue.popleft())      # 1（先进先出）
```

### 示例

```python
def is_balanced(text: str) -> bool:
    """用栈判断括号是否匹配。"""
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for ch in text:
        if ch in "([{":
            stack.append(ch)
        elif ch in pairs:
            if not stack or stack.pop() != pairs[ch]:
                return False
    return not stack

print(is_balanced("([]{})"))   # True
```

### 练习

1. 用队列实现「广度优先」遍历。
2. 用栈把十进制转二进制。

### 注意事项

- 队列用 `deque`，`list.pop(0)` 是 O(n)。
- 栈用 `list` 即可，均摊 O(1)。

### 常见错误

- 用 `list.pop(0)` 当队列，性能差。
- 空栈 `pop()` 抛 `IndexError`。

## linked-list

### 理论

链表由节点组成，每个节点存数据与指向下一节点的引用。插入/删除 O(1)（已知位置），查找 O(n)。相比数组无需连续内存，但随机访问慢。

### 代码

```python
class Node:
    """链表节点。"""

    def __init__(self, value: int, next: "Node | None" = None) -> None:
        self.value = value
        self.next = next

class LinkedList:
    """单向链表。"""

    def __init__(self) -> None:
        self.head: Node | None = None

    def push(self, value: int) -> None:
        self.head = Node(value, self.head)

    def to_list(self) -> list[int]:
        result, node = [], self.head
        while node:
            result.append(node.value)
            node = node.next
        return result

print(LinkedList().to_list())
```

### 示例

```python
def reverse(head: Node | None) -> Node | None:
    """反转链表。"""
    prev = None
    while head:
        head.next, prev, head = prev, head, head.next
    return prev
```

### 练习

1. 实现链表的按值删除。
2. 检测链表是否有环（快慢指针）。

### 注意事项

- 注意处理头节点与空链表边界。
- 修改指针顺序要小心，避免断链。

### 常见错误

- 遍历时未保存 `next`，反转后丢失后半段。
- 忘记处理空链表。

## recursion-dp

### 理论

递归把问题分解为更小的同类子问题，需有「基准情形」终止。若子问题被重复计算，可用动态规划（DP）——记忆化（自顶向下）或递推（自底向上）——把指数级降为多项式级。

### 代码

```python
# 朴素递归：O(2^n)
def fib_naive(n: int) -> int:
    return n if n < 2 else fib_naive(n - 1) + fib_naive(n - 2)

# 记忆化：O(n)
from functools import lru_cache

@lru_cache(maxsize=None)
def fib_memo(n: int) -> int:
    return n if n < 2 else fib_memo(n - 1) + fib_memo(n - 2)

print(fib_naive(10), fib_memo(50))
```

### 示例

```python
def climb_stairs(n: int) -> int:
    """每次走 1 或 2 阶，求到达第 n 阶的方法数（递推 DP）。"""
    if n <= 2:
        return n
    prev, cur = 1, 2
    for _ in range(3, n + 1):
        prev, cur = cur, prev + cur
    return cur

print(climb_stairs(5))   # 8
```

### 练习

1. 用 DP 求最长递增子序列长度（入门版）。
2. 用记忆化解决「硬币找零」问题。

### 注意事项

- 递归要有明确基准情形，防无限递归。
- Python 递归深度默认约 1000，深递归改用迭代。

### 常见错误

- 忘记基准情形导致 `RecursionError`。
- 重复计算子问题，性能指数级下降。
