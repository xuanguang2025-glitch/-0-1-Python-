'use client';

import { useMemo, useState } from 'react';
import { BookOpen, FileCode2, Play, Save, Star, Trash2, Wand2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCode } from '@/lib/format';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { usePythonRunner } from '@/hooks/usePythonRunner';
import { useToaster } from '@/hooks/useToast';
import { MonacoEditor } from '@/components/code/monaco-editor';
import { ResultPanel } from '@/components/code/result-panel';
import { PageContainer } from '@/components/layout/page-container';
import { Alert } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/input';
import { Navbar } from '@/components/layout/navbar';

interface Snippet {
  id: string;
  title: string;
  description: string;
  code: string;
}

const SNIPPETS: Snippet[] = [
  {
    id: 'hello',
    title: 'Hello World',
    description: '最基础的输出与变量',
    code: `name = "Python"\nprint(f"Hello, {name}!")\nprint("1 + 1 =", 1 + 1)\n`,
  },
  {
    id: 'loop',
    title: '循环与条件',
    description: 'for / if 的常见组合',
    code: `for i in range(1, 16):\n    if i % 15 == 0:\n        print("FizzBuzz")\n    elif i % 3 == 0:\n        print("Fizz")\n    elif i % 5 == 0:\n        print("Buzz")\n    else:\n        print(i)\n`,
  },
  {
    id: 'comprehension',
    title: '列表推导式',
    description: '一行写过滤 + 变换',
    code: `numbers = list(range(1, 21))\nevens = [n for n in numbers if n % 2 == 0]\nsquares = {n: n ** 2 for n in evens}\nprint(evens)\nprint(squares)\n`,
  },
  {
    id: 'function',
    title: '函数与默认参数',
    description: '避免可变默认参数陷阱',
    code: `def add_item(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)\n    return items\n\nprint(add_item("a"))\nprint(add_item("b"))\n`,
  },
  {
    id: 'dict',
    title: '字典与计数',
    description: '统计词频的经典写法',
    code: `text = "the quick brown fox jumps over the lazy dog the fox"\ncounter = {}\nfor word in text.split():\n    counter[word] = counter.get(word, 0) + 1\n\nfor word, count in sorted(counter.items(), key=lambda kv: -kv[1]):\n    print(f"{word:<6} {count}")\n`,
  },
  {
    id: 'class',
    title: '面向对象',
    description: '类、属性与方法',
    code: `class BankAccount:\n    def __init__(self, owner: str, balance: float = 0.0) -> None:\n        self.owner = owner\n        self.balance = balance\n\n    def deposit(self, amount: float) -> None:\n        if amount <= 0:\n            raise ValueError("存款金额必须为正数")\n        self.balance += amount\n\n    def __repr__(self) -> str:\n        return f"BankAccount({self.owner!r}, {self.balance:.2f})"\n\n\naccount = BankAccount("小明", 100)\naccount.deposit(50)\nprint(account)\n`,
  },
  {
    id: 'error',
    title: '异常处理',
    description: 'try / except / else / finally',
    code: `def safe_divide(a, b):\n    try:\n        result = a / b\n    except ZeroDivisionError as exc:\n        print("除零错误：", exc)\n        return None\n    else:\n        return result\n    finally:\n        print("计算结束")\n\nprint(safe_divide(10, 2))\nprint(safe_divide(1, 0))\n`,
  },
];

const STORAGE_KEY = 'playground.snippets';

/** 练习场：单文件快速实验 + 常用代码片段库。 */
export default function PlaygroundPage(): React.ReactElement {
  const toaster = useToaster();
  const runner = usePythonRunner();
  const [code, setCode] = useState(SNIPPETS[0].code);
  const [stdin, setStdin] = useState('');
  const [activeSnippet, setActiveSnippet] = useState(SNIPPETS[0].id);
  const [saved, setSaved] = useLocalStorage<{ title: string; code: string }[]>(STORAGE_KEY, []);

  const lines = useMemo(() => code.split('\n').length, [code]);

  const run = async (): Promise<void> => {
    await runner.run([{ path: 'main.py', content: code }], { entry: 'main.py', stdin: stdin || undefined });
  };

  const saveSnippet = (): void => {
    const title = window.prompt('给这段代码起个名字', `片段 ${saved.length + 1}`);
    if (!title) return;
    setSaved((prev) => [...prev, { title, code }]);
    toaster.success('已保存到我的片段', title);
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <PageContainer
        title="练习场"
        description="随手写一段 Python 试试看。左侧挑片段，改一改再运行。"
        showNavbar={false}
        showFooter={false}
        actions={
          <>
            <Badge variant="secondary" className="font-mono text-[10px]">
              {lines} 行
            </Badge>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setCode(formatCode(code, 'python'));
                toaster.success('已格式化');
              }}
            >
              <Wand2 className="h-3.5 w-3.5" />
              格式化
            </Button>
            <Button size="sm" variant="outline" onClick={saveSnippet}>
              <Save className="h-3.5 w-3.5" />
              保存片段
            </Button>
            <Button size="sm" loading={runner.running} onClick={() => void run()}>
              <Play className="h-3.5 w-3.5" />
              运行
            </Button>
          </>
        }
      >
        <Alert
          variant="info"
          title="快捷键：Ctrl + Enter 运行"
          description="练习场不需要创建文件，适合验证语法、试算法。需要多文件工程请用 /editor。"
          className="mb-4"
        />

        <div className="grid gap-4 lg:grid-cols-[240px_minmax(0,1fr)_340px]">
          {/* 片段库 */}
          <aside className="space-y-3">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-1.5">
                  <BookOpen className="h-4 w-4 text-primary" />
                  代码片段
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {SNIPPETS.map((snippet) => (
                  <button
                    key={snippet.id}
                    type="button"
                    onClick={() => {
                      setActiveSnippet(snippet.id);
                      setCode(snippet.code);
                    }}
                    className={cn(
                      'w-full rounded-md px-2.5 py-2 text-left transition-colors',
                      activeSnippet === snippet.id ? 'bg-primary/12 text-primary' : 'hover:bg-muted',
                    )}
                  >
                    <p className="text-[12.5px] font-medium">{snippet.title}</p>
                    <p className="text-[11px] text-muted-foreground">{snippet.description}</p>
                  </button>
                ))}
              </CardContent>
            </Card>

            {saved.length > 0 ? (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-1.5">
                    <Star className="h-4 w-4 text-accent" />
                    我的片段
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  {saved.map((item, index) => (
                    <div key={`${item.title}-${index}`} className="flex items-center gap-1">
                      <button
                        type="button"
                        className="min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-muted"
                        onClick={() => setCode(item.code)}
                      >
                        {item.title}
                      </button>
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        aria-label="删除片段"
                        onClick={() => setSaved((prev) => prev.filter((_, i) => i !== index))}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </aside>

          {/* 编辑器 */}
          <div className="space-y-3">
            <div className="overflow-hidden rounded-lg border border-border">
              <div className="flex items-center gap-2 border-b border-border bg-card/60 px-3 py-2">
                <FileCode2 className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="font-mono text-[12px]">main.py</span>
                <span className="ml-auto text-[11px] text-muted-foreground">Python 3 · 自动补全 · 折叠</span>
              </div>
              <MonacoEditor
                value={code}
                onChange={setCode}
                height={420}
                language="python"
                onRun={() => void run()}
              />
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle>标准输入（stdin）</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  rows={3}
                  value={stdin}
                  onChange={(event) => setStdin(event.target.value)}
                  placeholder="如果代码里用了 input()，把输入值写在这里，每行一个"
                  className="font-mono text-[12px]"
                />
              </CardContent>
            </Card>
          </div>

          {/* 结果 */}
          <div className="h-[560px] overflow-hidden rounded-lg border border-border bg-card/40">
            <ResultPanel
              result={runner.result}
              running={runner.running}
              error={runner.error}
              emptyHint="点击「运行」查看输出，运行结果会保留在这里"
              className="h-full overflow-auto"
            />
          </div>
        </div>
      </PageContainer>
    </div>
  );
}
