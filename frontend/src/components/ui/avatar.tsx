'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { initials } from '@/lib/utils';

export interface AvatarProps {
  src?: string | null;
  name?: string | null;
  size?: number;
  className?: string;
  ring?: boolean;
}

/** 头像：加载失败或未设置时回退为昵称首字母。 */
export function Avatar({ src, name, size = 32, className, ring = false }: AvatarProps): React.ReactElement {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(src) && !failed;

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary/15 text-[11px] font-semibold uppercase text-primary',
        ring && 'ring-2 ring-primary/30',
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.36) }}
      title={name ?? undefined}
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src ?? ''}
          alt={name ?? '头像'}
          width={size}
          height={size}
          className="h-full w-full object-cover"
          onError={() => setFailed(true)}
        />
      ) : (
        initials(name)
      )}
    </span>
  );
}
