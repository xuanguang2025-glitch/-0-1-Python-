# 阶段 8 · 面向对象

## class-basics

### 理论

类（class）是对象的模板，把「数据（属性）」和「行为（方法）」封装在一起。对象是类的实例。`self` 表示实例本身，方法的第一个参数必须是 `self`。

### 代码

```python
class Dog:
    """一只狗。"""

    species = "Canis familiaris"   # 类属性

    def __init__(self, name: str, age: int) -> None:
        self.name = name           # 实例属性
        self.age = age

    def bark(self) -> str:
        return f"{self.name} 汪汪叫"

dog = Dog("旺财", 3)
print(dog.bark(), dog.species, dog.age)
```

### 示例

```python
class Counter:
    """简易计数器。"""

    def __init__(self) -> None:
        self.value = 0

    def add(self, n: int = 1) -> int:
        self.value += n
        return self.value

c = Counter()
c.add(); c.add(5)
print(c.value)   # 6
```

### 练习

1. 定义一个 `Student` 类，含姓名、成绩与平均分方法。
2. 定义 `Rectangle` 类，提供面积与周长的属性。

### 注意事项

- 类名用大驼峰 `PascalCase`，方法/属性用小写加下划线。
- 每个类写 docstring 说明职责。

### 常见错误

- 忘记在方法里写 `self`。
- 用可变对象（如列表）做类属性，被所有实例共享。

## init-method

### 理论

`__init__` 是初始化方法，在实例创建后自动调用，用于给实例属性赋初值。它不是构造器本身（`__new__` 才是），但对日常使用足够了。

### 代码

```python
class Account:
    """银行账户。"""

    def __init__(self, owner: str, balance: float = 0.0) -> None:
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("存款必须为正数")
        self.balance += amount

acc = Account("张三", 100.0)
acc.deposit(50)
print(acc.balance)   # 150.0
```

### 示例

```python
class Point:
    """二维坐标点。"""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point(x={self.x}, y={self.y})"

print(Point(1, 2))
```

### 练习

1. 为 `Account` 增加 `withdraw` 方法，余额不足时报错。
2. 给类的 `__init__` 参数加上类型注解与默认值。

### 注意事项

- `__init__` 不返回任何值（返回 `None`）。
- 参数给默认值时避免可变默认参数。

### 常见错误

- `def __init__(self)` 写成 `def init(self)`。
- 用 `list` 作默认参数导致实例间串数据。

## instance-class-attr

### 理论

实例属性属于具体对象，各自独立；类属性属于类，被所有实例共享。查找顺序：先找实例，再找类。可变类属性是常见陷阱。

### 代码

```python
class Employee:
    company = "PYTHON LAB"        # 类属性

    def __init__(self, name: str) -> None:
        self.name = name          # 实例属性

a = Employee("A")
b = Employee("B")
print(a.company, b.company)       # 都是 PYTHON LAB
a.company = "Other"               # 只在实例 a 上加了同名属性
print(a.company, b.company)       # Other PYTHON LAB
```

### 示例

```python
class Team:
    """演示可变类属性的坑与正确写法。"""

    def __init__(self) -> None:
        self.members: list[str] = []   # 每个实例独立，正确

t1, t2 = Team(), Team()
t1.members.append("张三")
print(t1.members, t2.members)        # ['张三'] []
```

### 练习

1. 用类属性统计创建的实例数量。
2. 演示把列表放类属性时两个实例互相污染的现象。

### 注意事项

- 需要「实例隔离」的数据放实例属性。
- 常量类属性用大写命名。

### 常见错误

- 用 `list`/`dict` 当类属性并直接 `append`，跨实例污染。
- 误以为 `a.company = x` 会改类属性。

## inheritance

### 理论

继承让子类复用父类代码并扩展。`class Child(Parent)` 声明继承；子类可重写（override）父类方法，并通过 `super()` 调用父类实现。

### 代码

```python
class Animal:
    """动物基类。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def speak(self) -> str:
        return "..."

class Cat(Animal):
    """猫。"""

    def speak(self) -> str:
        return f"{self.name} 喵"

class Dog(Animal):
    """狗。"""

    def speak(self) -> str:
        return f"{self.name} 汪"

for animal in (Cat("咪咪"), Dog("旺财")):
    print(animal.speak())
```

### 示例

```python
class Logger:
    """基础日志器。"""

    def log(self, msg: str) -> None:
        print(msg)

class TimestampLogger(Logger):
    """带时间戳的日志器，复用父类并增强。"""

    def log(self, msg: str) -> None:
        from datetime import datetime
        super().log(f"[{datetime.now():%H:%M:%S}] {msg}")

TimestampLogger().log("启动完成")
```

### 练习

1. 为 `Animal` 增加 `eat()`，让子类继承。
2. 用继承实现 `Shape` 基类与 `Circle`、`Square` 子类。

### 注意事项

- 优先组合优于继承，继承层级不要太深。
- 子类 `__init__` 记得调 `super().__init__()`。

### 常见错误

- 忘记调 `super().__init__()`，父类属性缺失。
- 继承层级过深导致难以维护。

## polymorphism

### 理论

多态指「同一接口，不同实现」。调用方只依赖抽象（同名方法），运行时按实际对象类型执行对应逻辑。Python 是「鸭子类型」：只要有需要的方法就能用，不必显式继承。

### 代码

```python
class Duck:
    def quack(self) -> str:
        return "嘎嘎"

class Person:
    def quack(self) -> str:
        return "我在模仿鸭子"

def make_it_quack(thing) -> None:
    """只要实现了 quack() 就能调用。"""
    print(thing.quack())

make_it_quack(Duck())
make_it_quack(Person())
```

### 示例

```python
from typing import Protocol

class Shape(Protocol):
    """形状协议：任何实现了 area() 的对象都算。"""

    def area(self) -> float: ...

class Circle:
    def __init__(self, r: float) -> None:
        self.r = r

    def area(self) -> float:
        return 3.14159 * self.r ** 2

def total_area(shapes: list[Shape]) -> float:
    return sum(s.area() for s in shapes)

print(total_area([Circle(1), Circle(2)]))
```

### 练习

1. 用鸭子类型实现可迭代对象的统一处理。
2. 用 `Protocol` 定义「可保存」协议并让两个类满足。

### 注意事项

- 多态接口要稳定、语义清晰。
- `Protocol` 做静态检查，运行时不强制。

### 常见错误

- 依赖具体类型做大量 `isinstance` 判断，丧失多态优势。
- 接口命名不一致，调用方必须分支处理。

## mro

### 理论

MRO（Method Resolution Order，方法解析顺序）决定多继承时「先找哪个类」。Python 用 C3 线性化算法，可用 `Class.__mro__` 查看顺序。多继承从左到右、从子到父查找。

### 代码

```python
class A:
    def who(self) -> str:
        return "A"

class B(A):
    def who(self) -> str:
        return "B"

class C(A):
    def who(self) -> str:
        return "C"

class D(B, C):
    pass

print([cls.__name__ for cls in D.__mro__])   # ['D', 'B', 'C', 'A', 'object']
print(D().who())                             # B（沿 MRO 第一个命中的）
```

### 示例

```python
class Base:
    def __init__(self) -> None:
        print("Base")

class Left(Base):
    def __init__(self) -> None:
        print("Left")
        super().__init__()

class Right(Base):
    def __init__(self) -> None:
        print("Right")
        super().__init__()

class Diamond(Left, Right):
    def __init__(self) -> None:
        print("Diamond")
        super().__init__()

Diamond()   # Diamond -> Left -> Right -> Base
```

### 练习

1. 打印一个多继承类的 MRO 并解释输出顺序。
2. 用 `super()` 链式调用验证协作式初始化。

### 注意事项

- 多继承虽强，但优先用 mixin 组合少量职责。
- 统一使用 `super()` 而非直接写父类名。

### 常见错误

- 多继承中不使用 `super()`，导致父类初始化被跳过。
- 设计出 MRO 冲突（`TypeError: Cannot create a consistent MRO`）。

## magic-methods

### 理论

魔术方法（dunder）让对象支持内置语法：`__str__`/`__repr__`（打印）、`__len__`（长度）、`__eq__`/`__hash__`（等价）、`__add__`（加法）、`__getitem__`（索引）、`__call__`（可调用）等。

### 代码

```python
class Vector:
    """二维向量，支持加法与打印。"""

    def __init__(self, x: float, y: float) -> None:
        self.x, self.y = x, y

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y)

    def __repr__(self) -> str:
        return f"Vector({self.x}, {self.y})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vector) and (self.x, self.y) == (other.x, other.y)

v = Vector(1, 2) + Vector(3, 4)
print(v)                       # Vector(4, 6)
print(Vector(1, 1) == Vector(1, 1))   # True
```

### 示例

```python
class Playlist:
    """支持 len() 与索引的播放列表。"""

    def __init__(self, songs: list[str]) -> None:
        self.songs = songs

    def __len__(self) -> int:
        return len(self.songs)

    def __getitem__(self, i: int) -> str:
        return self.songs[i]

pl = Playlist(["A", "B", "C"])
print(len(pl), pl[1], list(pl))
```

### 练习

1. 为 `Vector` 加上 `__mul__`（与标量相乘）。
2. 实现一个可比较大小的 `Card` 类。

### 注意事项

- 定义 `__eq__` 通常也要定义 `__hash__`（否则不可哈希）。
- `__repr__` 面向开发者，`__str__` 面向用户。

### 常见错误

- 重写 `__eq__` 后对象无法放进 `set`（`__hash__` 变 `None`）。
- `__getitem__` 不处理越界，抛了非预期异常。

## property

### 理论

`@property` 把方法伪装成属性访问，实现「读取时计算/校验」而不改变调用方式。配合 `@x.setter` 可做赋值校验，实现封装与数据保护。

### 代码

```python
class Circle:
    """半径带校验的圆。"""

    def __init__(self, radius: float) -> None:
        self.radius = radius

    @property
    def radius(self) -> float:
        return self._radius

    @radius.setter
    def radius(self, value: float) -> None:
        if value <= 0:
            raise ValueError("半径必须为正数")
        self._radius = value

    @property
    def area(self) -> float:
        return 3.14159 * self._radius ** 2

c = Circle(2)
print(c.area)      # 12.56636
# c.radius = -1    # 抛 ValueError
```

### 示例

```python
class Temperature:
    """摄氏/华氏互转。"""

    def __init__(self, celsius: float = 0.0) -> None:
        self._c = celsius

    @property
    def fahrenheit(self) -> float:
        return self._c * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value: float) -> None:
        self._c = (value - 32) * 5 / 9

t = Temperature(25)
print(t.fahrenheit)     # 77.0
```

### 练习

1. 给 `Account.balance` 加只读属性与存入校验。
2. 实现「只读属性」——只定义 getter，不定义 setter。

### 注意事项

- 私有属性用单下划线 `_x` 约定（非强制）。
- property 适合轻量计算，避免放耗时逻辑。

### 常见错误

- setter 内误写成 `self.radius = value` 造成无限递归。
- 在 `__init__` 里绕过校验直接赋 `_radius`。

## dataclass

### 理论

`@dataclass` 自动生成 `__init__`、`__repr__`、`__eq__`，适合「以数据为主」的类，减少样板代码。支持默认值、`field()`、`frozen=True`（不可变）、`order=True`（可比较）。

### 代码

```python
from dataclasses import dataclass, field

@dataclass
class User:
    """用户数据模型。"""

    name: str
    age: int = 0
    tags: list[str] = field(default_factory=list)

u = User("张三", 20, ["python"])
print(u)                       # User(name='张三', age=20, tags=['python'])
print(u == User("张三", 20, ["python"]))   # True
```

### 示例

```python
from dataclasses import dataclass

@dataclass(frozen=True, order=True)
class Version:
    """可排序、不可变的版本号。"""

    major: int
    minor: int

print(Version(1, 0) < Version(1, 2))   # True
```

### 练习

1. 用 dataclass 定义 `Point` 并比较相等。
2. 定义带默认值的 dataclass，注意字段顺序。

### 注意事项

- 有默认值的字段必须排在无默认值字段之后。
- 可变默认值必须用 `field(default_factory=...)`。

### 常见错误

- 直接写 `tags: list = []`，触发 `ValueError: mutable default`。
- `frozen=True` 后仍尝试赋值，抛 `FrozenInstanceError`。
