# 阶段 11 · 数据库

## sql-basics

### 理论

SQL 是关系型数据库的查询语言。核心操作分 DDL（建表、改表）与 DML（增删改查）。表由行（记录）与列（字段）组成，字段有类型与约束（主键、非空、唯一、默认值）。

### 代码

```sql
CREATE TABLE users (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT    NOT NULL,
    email   TEXT    NOT NULL UNIQUE,
    age     INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id  INTEGER NOT NULL REFERENCES users(id),
    title    TEXT NOT NULL
);
```

### 示例

```sql
-- 查看表结构（SQLite）
PRAGMA table_info(users);

-- 添加列
ALTER TABLE users ADD COLUMN bio TEXT;
```

### 练习

1. 设计一张 `products` 表，含主键、名称、价格、库存。
2. 为 `email` 加唯一约束并验证重复插入失败。

### 注意事项

- 主键一般用自增整数或 UUID。
- 名称、邮箱等关键字段加约束保证数据质量。

### 常见错误

- 忘记主键，插入重复数据难以区分。
- 字段类型选择不当（金额用浮点导致精度问题）。

## crud-sql

### 理论

CRUD 指增（INSERT）、查（SELECT）、改（UPDATE）、删（DELETE）。`WHERE` 过滤行，`ORDER BY` 排序，`LIMIT` 限制数量，`GROUP BY` 分组聚合。

### 代码

```sql
INSERT INTO users (name, email, age) VALUES ('张三', 'a@x.com', 20);
INSERT INTO users (name, email) VALUES ('李四', 'b@x.com');

SELECT id, name, age FROM users WHERE age >= 18 ORDER BY age DESC LIMIT 10;

UPDATE users SET age = 21 WHERE name = '张三';

DELETE FROM users WHERE email = 'b@x.com';
```

### 示例

```sql
-- 聚合统计
SELECT COUNT(*) AS total, AVG(age) AS avg_age, MAX(age) AS max_age FROM users;

-- 分组
SELECT age, COUNT(*) AS cnt FROM users GROUP BY age HAVING cnt > 1;
```

### 练习

1. 写一组完整 CRUD 语句操作 `products` 表。
2. 用聚合函数统计各年龄段人数。

### 注意事项

- 先 `SELECT` 确认条件，再 `UPDATE`/`DELETE`。
- 更新/删除务必带 `WHERE`，否则影响全表。

### 常见错误

- `UPDATE`/`DELETE` 漏写 `WHERE`，全表被改/删。
- `HAVING` 与 `WHERE` 混用（`WHERE` 过滤行，`HAVING` 过滤分组）。

## join-query

### 理论

`JOIN` 把多表按关联字段组合。`INNER JOIN` 取交集，`LEFT JOIN` 保留左表全部，`RIGHT JOIN` 保留右表，`FULL JOIN` 全保留。`ON` 指定连接条件。

### 代码

```sql
-- 每个用户及其文章数（含没有文章的用户）
SELECT u.id, u.name, COUNT(p.id) AS post_count
FROM users u
LEFT JOIN posts p ON p.user_id = u.id
GROUP BY u.id, u.name
ORDER BY post_count DESC;
```

### 示例

```sql
-- 只取有文章的用户
SELECT u.name, p.title
FROM users u
INNER JOIN posts p ON p.user_id = u.id;

-- 查找没有任何文章的用户
SELECT u.name
FROM users u
LEFT JOIN posts p ON p.user_id = u.id
WHERE p.id IS NULL;
```

### 练习

1. 用三张表做关联查询（用户-文章-评论）。
2. 求每个用户最近一篇文章的标题。

### 注意事项

- 连接字段建立索引可大幅提速。
- `LEFT JOIN` 后用 `WHERE` 过滤右表字段要小心（会退化为内连接）。

### 常见错误

- 忘记 `ON` 条件产生笛卡尔积。
- 在 `LEFT JOIN` 后用 `WHERE p.x = 1` 把无匹配行过滤掉。

## sqlite-python

### 理论

`sqlite3` 是内置模块，连接本地文件数据库，零配置。流程：`connect()` → `cursor()` → `execute()` → `commit()`/`fetchall()`。参数化用 `?` 占位符防注入。

### 代码

```python
import sqlite3

conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
cur.execute("INSERT INTO users (name) VALUES (?)", ("张三",))
conn.commit()
cur.execute("SELECT id, name FROM users")
print(cur.fetchall())   # [(1, '张三')]
conn.close()
```

### 示例

```python
import sqlite3

def get_user(email: str) -> tuple | None:
    """参数化查询，防止 SQL 注入。"""
    with sqlite3.connect("app.db") as conn:
        cur = conn.execute("SELECT id, name FROM users WHERE email = ?", (email,))
        return cur.fetchone()
```

### 练习

1. 用 `sqlite3` 完成一次完整的增删改查。
2. 用 `executemany` 批量插入 100 条数据。

### 注意事项

- 始终用参数化查询，不要字符串拼接 SQL。
- 写操作后要 `commit()`。

### 常见错误

- 忘记 `commit()`，数据丢失。
- 用 f-string 拼 SQL 造成注入风险。

## transaction

### 理论

事务是一组原子操作，要么全部成功（COMMIT），要么全部回滚（ROLLBACK）。满足 ACID：原子性、一致性、隔离性、持久性。SQLite 默认自动提交，可用 `BEGIN` 显式控制。

### 代码

```python
import sqlite3

conn = sqlite3.connect("bank.db")
try:
    conn.execute("BEGIN")
    conn.execute("UPDATE accounts SET balance = balance - 100 WHERE id = 1")
    conn.execute("UPDATE accounts SET balance = balance + 100 WHERE id = 2")
    conn.commit()
except Exception:
    conn.rollback()      # 任一步失败，全部撤销
    raise
finally:
    conn.close()
```

### 示例

```python
import sqlite3

def transfer(db: str, src: int, dst: int, amount: float) -> None:
    """转账：要么都成功，要么都不发生。"""
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (amount, src))
        conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, dst))
```

### 练习

1. 模拟转账中途抛异常，验证回滚生效。
2. 用事务批量插入并保证要么全成功要么全失败。

### 注意事项

- 事务中避免长时间持有锁。
- 异常路径务必 `rollback()`。

### 常见错误

- 异常后未回滚，事务悬挂。
- 长事务阻塞并发写。

## index-basics

### 理论

索引像书的目录，加速 `WHERE`/`JOIN`/`ORDER BY`。B-tree 索引最常见。代价：占空间、拖慢写入。对高选择性、经常查询的列建索引收益最大。

### 代码

```sql
CREATE INDEX idx_users_email ON users(email);
CREATE UNIQUE INDEX idx_users_username ON users(username);

-- 查看查询计划（SQLite）
EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'a@x.com';
```

### 示例

```sql
-- 复合索引：区分顺序很重要
CREATE INDEX idx_posts_user_created ON posts(user_id, created_at);

-- 可用于 user_id 查询，也可用于 user_id + created_at 排序
SELECT * FROM posts WHERE user_id = 1 ORDER BY created_at DESC;
```

### 练习

1. 对比建索引前后查询计划的变化。
2. 为 `posts(user_id)` 建索引并验证使用情况。

### 注意事项

- 索引不是越多越好，写入频繁的表要克制。
- 复合索引遵循「最左前缀」原则。

### 常见错误

- 对低基数列（如性别）建索引，收益低。
- 在索引列上用函数导致索引失效。

## sqlalchemy-orm

### 理论

ORM（对象关系映射）把数据库表映射为 Python 类。SQLAlchemy 2.0 用声明式模型：`DeclarativeBase` + `Mapped`/`mapped_column`。用 Session 管理查询与事务，避免手写字符串 SQL。

### 代码

```python
from sqlalchemy import String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    age: Mapped[int] = mapped_column(default=0)

engine = create_engine("sqlite:///app.db")
Base.metadata.create_all(engine)

with Session(engine) as session:
    session.add(User(name="张三", age=20))
    session.commit()
    users = session.scalars(select(User).where(User.age >= 18)).all()
    print([u.name for u in users])
```

### 示例

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

def get_by_name(session: Session, name: str) -> User | None:
    """按名称查询单个用户。"""
    return session.scalars(select(User).where(User.name == name)).first()
```

### 练习

1. 定义 `Post` 模型并与 `User` 建立关联。
2. 用 ORM 完成一次增删改查。

### 注意事项

- 用参数化查询（ORM 已自动处理）。
- Session 用完即关（`with` 上下文）。

### 常见错误

- Session 长期不关，连接泄漏。
- 忘记 `commit()`，改动未持久化。

## db-design

### 理论

表结构设计遵循范式以消除冗余：1NF（字段原子）、2NF（非主属性完全依赖主键）、3NF（不传递依赖）。也要权衡反范式（为查询性能适度冗余）。关系用外键表达：一对多、多对多（需要中间表）。

### 代码

```python
# 多对多：学生 - 选课 - 课程
# students(id, name)
# courses(id, title)
# enrollments(student_id, course_id, score)   <-- 中间表

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

class Enrollment(Base):
    __tablename__ = "enrollments"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    score: Mapped[float] = mapped_column(default=0.0)
```

### 示例

```python
# 一对多：user -> posts
# users(id, name)
# posts(id, user_id FK, title)

# 反范式示例：在订单表冗余 user_name，避免频繁 join
```

### 练习

1. 为「博客系统」设计表结构（用户/文章/评论/标签）。
2. 用 ER 图描述关系并指出外键。

### 注意事项

- 外键保证引用完整性。
- 命名一致、加注释，便于维护。

### 常见错误

- 冗余字段无同步机制导致数据不一致。
- 缺外键约束，产生孤儿数据。

## orm-query

### 理论

SQLAlchemy 2.0 用 `select()` 构建查询，支持 `where`、`join`、`group_by`、`order_by`、`limit`。可用 `func` 调用 SQL 函数，`relationship` 做预加载（`selectinload`）避免 N+1 查询。

### 代码

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

# 聚合
stmt = select(func.count(User.id), func.avg(User.age))
total, avg_age = session.execute(stmt).one()

# 关联预加载，避免 N+1
stmt = select(User).options(selectinload(User.posts)).where(User.age >= 18)
users = session.scalars(stmt).all()
```

### 示例

```python
from sqlalchemy import select

def top_active(session: Session, limit: int = 10) -> list[User]:
    """按文章数排序取最活跃用户。"""
    stmt = (
        select(User)
        .join(User.posts)
        .group_by(User.id)
        .order_by(func.count(Post.id).desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))
```

### 练习

1. 用 ORM 实现分页查询。
2. 用 `selectinload` 优化一处 N+1 查询。

### 注意事项

- 惰性加载在循环中易触发 N+1，改用预加载。
- 复杂查询可先用 SQL 验证再转 ORM。

### 常见错误

- 循环里访问关联属性，触发大量查询。
- 忘记 `order_by` 导致分页结果不稳定。
