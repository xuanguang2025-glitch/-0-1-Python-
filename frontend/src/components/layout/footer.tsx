import Link from 'next/link';
import { MAIN_NAV, SITE_NAME } from '@/lib/constants';

/** 站点页脚。 */
export function Footer(): React.ReactElement {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-12 border-t border-border bg-card/40">
      <div className="mx-auto grid max-w-[1400px] gap-8 px-4 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo.svg" alt="" className="h-7 w-7" />
            <span className="text-[15px] font-bold">{SITE_NAME}</span>
          </div>
          <p className="text-[12px] leading-relaxed text-muted-foreground">
            从零开始，系统掌握 Python。18 个阶段、在线编辑器、智能判题与 AI 导师，一站式编程学习平台。
          </p>
        </div>

        <div className="space-y-2">
          <p className="text-[13px] font-semibold">学习</p>
          {MAIN_NAV.filter((item) => ['/courses', '/learn', '/problems', '/projects'].includes(item.href)).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block text-[12px] text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-[13px] font-semibold">工具</p>
          {[
            { label: '在线编辑器', href: '/editor' },
            { label: '练习场', href: '/playground' },
            { label: 'AI 导师', href: '/ai-tutor' },
            { label: '学习统计', href: '/statistics' },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block text-[12px] text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-[13px] font-semibold">关于</p>
          {[
            { label: '学习社区', href: '/community' },
            { label: '我的收藏', href: '/bookmarks' },
            { label: '错题本', href: '/wrong-answers' },
            { label: '通知中心', href: '/notifications' },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block text-[12px] text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
      <div className="border-t border-border px-4 py-4 text-center text-[11px] text-muted-foreground">
        © {year} {SITE_NAME} · 学习语法，编写代码，解决问题，完成真实项目。
      </div>
    </footer>
  );
}
