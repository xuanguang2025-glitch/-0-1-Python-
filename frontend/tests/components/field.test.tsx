// @vitest-environment jsdom
/**
 * `src/components/ui/input.tsx` 的 `Field` —— label 与控件的自动关联。
 *
 * ## 背景
 * 全站 42 个 `<Field>` 调用点**无一传 `htmlFor`**，label 与控件在 DOM 层是孤立的，
 * 屏幕阅读器无法把两者关联。`Field` 现用 `useId()` + `cloneElement` 自动建立关联，
 * 调用方零改动全站生效。
 *
 * ## 关键设计：HTML 规范的 labelable elements 白名单
 * 判断依据不是「children 是不是合法元素」，而是「该元素**是否可被 `<label for>` 关联**」。
 * 这一点最容易改坏 —— `profile/page.tsx:153` 的「时区」字段 children 是一个**合法的
 * `<div>` 元素**（包着一组 `<button>`），若按「合法元素就注入」处理，会生成
 * `for` 指向不可标签化元素的**无效关联**：比完全没有关联更糟（点击无反应、
 * 屏幕阅读器忽略、检查器报更多问题）。故必须按白名单降级。
 *
 * @see https://html.spec.whatwg.org/multipage/forms.html#category-label
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { Field, Input, Textarea } from '@/components/ui/input';
import { Select } from '@/components/ui/select';

describe('Field · 自动建立 label↔控件关联', () => {
  it('★ Input：label 的 for 与 input 的 id 配对正确', () => {
    render(
      <Field label="邮箱">
        <Input />
      </Field>,
    );

    const input = screen.getByLabelText('邮箱');
    const label = screen.getByText('邮箱').closest('label');

    expect(label).toBeTruthy();
    expect(input.tagName).toBe('INPUT');
    // 直接对照验收标准：for 与 id 严格配对
    expect(label!.getAttribute('for')).toBe(input.getAttribute('id'));
    expect(input.getAttribute('id')).toBeTruthy();
  });

  it('★ getByLabelText 能取到控件（浏览器层关联真实成立）', () => {
    render(
      <Field label="用户名">
        <Input />
      </Field>,
    );

    // 若 for/id 没配对，getByLabelText 会抛错 —— 这是最贴近真实辅助技术的断言
    expect(screen.getByLabelText('用户名')).toBeInstanceOf(HTMLInputElement);
  });

  it('Select / Textarea 同样建立关联', () => {
    const { rerender } = render(
      <Field label="学习模式">
        <Select options={[{ value: 'a', label: 'A' }]} />
      </Field>,
    );
    expect(screen.getByLabelText('学习模式').tagName).toBe('SELECT');

    rerender(
      <Field label="学习模式">
        <Textarea />
      </Field>,
    );
    expect(screen.getByLabelText('学习模式').tagName).toBe('TEXTAREA');
  });

  it('同一页面多个 Field 的 id 互不冲突', () => {
    render(
      <div>
        <Field label="旧密码">
          <Input />
        </Field>
        <Field label="新密码">
          <Input />
        </Field>
        <Field label="确认密码">
          <Input />
        </Field>
      </div>,
    );

    const old = screen.getByLabelText('旧密码');
    const neu = screen.getByLabelText('新密码');
    const confirm = screen.getByLabelText('确认密码');
    const ids = [old.getAttribute('id'), neu.getAttribute('id'), confirm.getAttribute('id')];

    expect(new Set(ids).size).toBe(3);
    ids.forEach((id) => expect(id).toBeTruthy());
  });

  it('useId 生成的 id 在重渲染间稳定（不会导致焦点/输入状态丢失）', () => {
    const { rerender } = render(
      <Field label="昵称">
        <Input defaultValue="abc" />
      </Field>,
    );
    const first = screen.getByLabelText('昵称').getAttribute('id');

    rerender(
      <Field label="昵称">
        <Input defaultValue="abc" />
      </Field>,
    );
    expect(screen.getByLabelText('昵称').getAttribute('id')).toBe(first);
  });
});

describe('Field · 白名单降级（不得产生无效关联）', () => {
  it('★ children 为 div 时：label 上不得有 for 属性', () => {
    // 对应 profile/page.tsx:153「时区」的真实结构：
    // <Field label="时区"><div><button/>...</div></Field>
    render(
      <Field label="时区">
        <div>
          <button type="button">UTC</button>
          <button type="button">Asia/Shanghai</button>
        </div>
      </Field>,
    );

    const label = screen.getByText('时区').closest('label');
    expect(label).toBeTruthy();
    // ★ 核心断言：div 不可标签化，绝不能生成 for —— 否则是无效关联
    expect(label!.hasAttribute('for')).toBe(false);
    // 按钮本身也不该被塞进 id
    expect(screen.getByRole('button', { name: 'UTC' }).hasAttribute('id')).toBe(false);
  });

  it('children 为 span / section 等其他容器时同样不生成 for', () => {
    const { rerender } = render(
      <Field label="A">
        <span>x</span>
      </Field>,
    );
    expect(screen.getByText('A').closest('label')!.hasAttribute('for')).toBe(false);

    rerender(
      <Field label="B">
        <section>y</section>
      </Field>,
    );
    expect(screen.getByText('B').closest('label')!.hasAttribute('for')).toBe(false);
  });

  it('★ button 不注入：可访问名不被 label 覆盖', () => {
    // button 自带可见文字、可访问名由内容派生。若用<label for> 关联，
    // 部分辅助技术（含 dom-accessibility-api）会用 label 文本覆盖按钮自身的名字：
    // 实测 <Field label="操作"><button>提交</button></Field> 的按钮名会从「提交」变成「操作」。
    // 那反而削弱可访问性，因此 button 被刻意排除出白名单。
    render(
      <Field label="操作">
        <button type="button">提交</button>
      </Field>,
    );

    const label = screen.getByText('操作').closest('label');
    expect(label!.hasAttribute('for')).toBe(false);
    // 按钮名仍是自身内容
    expect(screen.getByRole('button', { name: '提交' })).toBeTruthy();
  });

  it('children 为字符串 / null 时安全降级，不崩', () => {
    const { rerender } = render(<Field label="纯文本">some text</Field>);
    expect(screen.getByText('纯文本').closest('label')!.hasAttribute('for')).toBe(false);
    expect(screen.getByText('some text')).toBeTruthy();

    rerender(<Field label="空">{null}</Field>);
    expect(screen.getByText('空').closest('label')!.hasAttribute('for')).toBe(false);
  });

  it('children 为数组 / Fragment 时安全降级，不崩且不生成 for', () => {
    const { rerender } = render(
      <Field label="多控件">
        {[<Input key="a" />, <Input key="b" />]}
      </Field>,
    );
    expect(screen.getByText('多控件').closest('label')!.hasAttribute('for')).toBe(false);
    expect(screen.getAllByRole('textbox')).toHaveLength(2);

    rerender(
      <Field label="Fragment">
        <>
          <Input />
        </>
      </Field>,
    );
    expect(screen.getByText('Fragment').closest('label')!.hasAttribute('for')).toBe(false);
  });
});

describe('Field · 显式 htmlFor 优先', () => {
  it('传入 htmlFor 时用它，且不覆盖 children 已有的 id', () => {
    render(
      <Field label="外部关联" htmlFor="my-custom-id">
        <Input id="my-custom-id" />
      </Field>,
    );

    const input = screen.getByLabelText('外部关联');
    expect(input.getAttribute('id')).toBe('my-custom-id');
    expect(screen.getByText('外部关联').closest('label')!.getAttribute('for')).toBe('my-custom-id');
  });

  it('传了 htmlFor 但 children 不可标签化时，label 仍指向外部 id', () => {
    // 调用方显式声明「我的控件在别处」，应尊重调用方意图
    render(
      <>
        <Field label="在别处" htmlFor="external-target">
          <div>占位</div>
        </Field>
        <input id="external-target" />
      </>,
    );

    const label = screen.getByText('在别处').closest('label');
    expect(label!.getAttribute('for')).toBe('external-target');
    // 占位 div 不该被注入 id
    expect(screen.getByText('占位').hasAttribute('id')).toBe(false);
  });
});

describe('Field · 其它 props 不受影响', () => {
  it('required / hint / error 正常渲染', () => {
    const { rerender } = render(
      <Field label="昵称" required hint="展示在排行榜">
        <Input />
      </Field>,
    );
    expect(screen.getByText(/展示在排行榜/)).toBeTruthy();

    rerender(
      <Field label="昵称" error="该昵称已被占用">
        <Input />
      </Field>,
    );
    // error 存在时 hint 不再渲染（互斥）
    expect(screen.getByText('该昵称已被占用')).toBeTruthy();
    expect(screen.queryByText(/展示在排行榜/)).toBeNull();
  });
});
