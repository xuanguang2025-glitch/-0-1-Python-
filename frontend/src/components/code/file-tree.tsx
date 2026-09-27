'use client';

import { ChevronDown, ChevronRight, FileCode2, FilePlus2, FolderOpen, MoreVertical, PenLine, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Dropdown } from '@/components/ui/dropdown';
import { Input } from '@/components/ui/input';

export interface FileNode {
  path: string;
  content: string;
  /** 是否为入口文件（不可删除）。 */
  isEntry?: boolean;
}

export interface FileTreeProps {
  files: FileNode[];
  activePath: string;
  onSelect: (path: string) => void;
  onCreate?: (path: string, content: string) => void;
  onDelete?: (path: string) => void;
  onRename?: (from: string, to: string) => void;
  className?: string;
  /** 只读模式（项目步骤浏览用）。 */
  readOnly?: boolean;
}

/** 多文件树：新建 / 删除 / 重命名。 */
export function FileTree({
  files,
  activePath,
  onSelect,
  onCreate,
  onDelete,
  onRename,
  className,
  readOnly = false,
}: FileTreeProps): React.ReactElement {
  const [expanded, setExpanded] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  const commitCreate = (): void => {
    const name = newName.trim();
    if (!name) {
      setCreating(false);
      return;
    }
    const path = name.endsWith('.py') || name.endsWith('.txt') || name.endsWith('.md') ? name : `${name}.py`;
    if (files.some((file) => file.path === path)) {
      setCreating(false);
      setNewName('');
      return;
    }
    onCreate?.(path, '');
    setNewName('');
    setCreating(false);
  };

  const commitRename = (from: string): void => {
    const name = renameValue.trim();
    if (name && name !== from && !files.some((file) => file.path === name)) {
      onRename?.(from, name);
    }
    setRenaming(null);
    setRenameValue('');
  };

  return (
    <div className={cn('flex h-full flex-col', className)}>
      <div className="flex items-center gap-1 border-b border-border px-2.5 py-2">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="flex items-center gap-1 text-[12px] font-semibold text-muted-foreground transition-colors hover:text-foreground"
        >
          {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          <FolderOpen className="h-3.5 w-3.5" />
          文件
        </button>
        {!readOnly && onCreate ? (
          <Button
            variant="ghost"
            size="icon-sm"
            className="ml-auto"
            aria-label="新建文件"
            onClick={() => {
              setCreating(true);
              setExpanded(true);
            }}
          >
            <FilePlus2 className="h-3.5 w-3.5" />
          </Button>
        ) : null}
      </div>

      <div className="scroll-area flex-1 py-1">
        {expanded ? (
          <>
            {files.map((file) => {
              const active = file.path === activePath;
              return (
                <div
                  key={file.path}
                  className={cn(
                    'group flex items-center gap-1 px-2 py-1 text-[12.5px] transition-colors',
                    active ? 'bg-primary/12 text-primary' : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                  )}
                >
                  {renaming === file.path ? (
                    <Input
                      autoFocus
                      value={renameValue}
                      className="h-6 text-[12px]"
                      onChange={(event) => setRenameValue(event.target.value)}
                      onBlur={() => commitRename(file.path)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') commitRename(file.path);
                        if (event.key === 'Escape') setRenaming(null);
                      }}
                    />
                  ) : (
                    <>
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                        onClick={() => onSelect(file.path)}
                        title={file.path}
                      >
                        <FileCode2 className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate font-mono">{file.path}</span>
                      </button>
                      {!readOnly ? (
                        <Dropdown
                          align="end"
                          items={[
                            {
                              label: '重命名',
                              icon: <PenLine className="h-3.5 w-3.5" />,
                              onSelect: () => {
                                setRenaming(file.path);
                                setRenameValue(file.path);
                              },
                            },
                            {
                              label: '删除',
                              danger: true,
                              disabled: Boolean(file.isEntry),
                              icon: <Trash2 className="h-3.5 w-3.5" />,
                              separatorBefore: true,
                              onSelect: () => onDelete?.(file.path),
                            },
                          ]}
                          trigger={() => (
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              aria-label="文件操作"
                              className="opacity-0 transition-opacity group-hover:opacity-100"
                            >
                              <MoreVertical className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        />
                      ) : null}
                    </>
                  )}
                </div>
              );
            })}

            {creating ? (
              <div className="px-2 py-1">
                <Input
                  autoFocus
                  value={newName}
                  placeholder="main.py"
                  className="h-6 text-[12px]"
                  onChange={(event) => setNewName(event.target.value)}
                  onBlur={commitCreate}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commitCreate();
                    if (event.key === 'Escape') {
                      setCreating(false);
                      setNewName('');
                    }
                  }}
                />
              </div>
            ) : null}

            {files.length === 0 ? <p className="px-3 py-2 text-[12px] text-muted-foreground">暂无文件</p> : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
