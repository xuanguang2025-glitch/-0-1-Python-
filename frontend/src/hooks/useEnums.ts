'use client';

/**
 * 后端权威枚举字典。
 *
 * `GET /api/health/enums` 是枚举的唯一权威来源（见 docs/API.md）。
 * 该 hook 会缓存一次请求结果（进程级），并在后端不可用时回退到内置常量，
 * 保证页面在离线/降级场景下仍可渲染。
 */

import { useEffect, useState } from 'react';
import { healthApi } from '@/lib/api';
import type { EnumDictionary } from '@/lib/types';

/** 内置兜底字典（与后端当前版本一致，仅在后端不可达时使用）。 */
export const FALLBACK_ENUMS: EnumDictionary = {
  role: ['user', 'admin', 'superadmin'],
  user_status: ['active', 'suspended', 'deleted'],
  difficulty: ['easy', 'medium', 'hard', 'expert'],
  course_level: ['beginner', 'intermediate', 'advanced'],
  lesson_type: ['concept', 'practice', 'quiz', 'project'],
  problem_type: ['choice', 'judge', 'blank', 'completion', 'coding', 'debug', 'algorithm'],
  problem_category: [
    'basics',
    'strings',
    'lists',
    'dicts',
    'sets_tuples',
    'functions',
    'oop',
    'files',
    'exceptions',
    'regex',
    'algorithms',
    'data_structures',
    'stdlib',
    'debug',
    'concurrency',
  ],
  submission_status: [
    'pending',
    'judging',
    'accepted',
    'wrong_answer',
    'runtime_error',
    'time_limit_exceeded',
    'memory_limit_exceeded',
    'compile_error',
    'security_error',
    'internal_error',
  ],
  comparison: ['exact', 'trimmed', 'float', 'custom'],
  runner: ['sandbox', 'local'],
  progress_status: ['not_started', 'in_progress', 'completed'],
  mastery_level: ['none', 'weak', 'medium', 'strong', 'mastered'],
  mistake_error_type: ['concept', 'syntax', 'logic', 'runtime', 'timeout', 'style', 'output'],
  bookmark_kind: ['problem', 'lesson', 'project', 'snippet', 'challenge'],
  code_context_type: ['lesson', 'problem', 'project', 'playground'],
  code_source: ['manual', 'auto', 'submit'],
  learning_mode: ['free', 'system', 'exam', 'drill', 'project', 'challenge', 'ai'],
  session_type: ['lesson', 'problem', 'project', 'exam', 'playground', 'challenge', 'ai'],
  ai_mode: ['beginner', 'standard', 'advanced'],
  ai_scene: ['tutor', 'review', 'error', 'exam', 'free'],
  ai_message_role: ['system', 'user', 'assistant'],
  ai_message_kind: ['hint', 'approach', 'partial', 'full', 'explain', 'review', 'error_analysis', 'answer'],
  achievement_category: ['learning', 'practice', 'streak', 'project', 'social', 'special'],
  challenge_type: ['daily', 'weekly', 'monthly', 'special'],
  challenge_status: ['joined', 'in_progress', 'completed'],
  user_project_status: ['not_started', 'in_progress', 'completed'],
  exam_level: ['basic', 'intermediate', 'advanced'],
  exam_attempt_status: ['in_progress', 'graded', 'abandoned'],
  notification_type: ['system', 'achievement', 'daily', 'challenge', 'ai', 'admin'],
  announcement_level: ['info', 'warning', 'important'],
  tag_kind: ['problem', 'course', 'project', 'lesson', 'snippet'],
  theme_preference: ['light', 'dark', 'system'],
  ai_provider: ['openai', 'anthropic', 'gemini', 'deepseek', 'qwen', 'zhipu', 'moonshot', 'custom'],
};

let cache: EnumDictionary | null = null;
let inflight: Promise<EnumDictionary> | null = null;

/** 拉取（或复用缓存的）枚举字典。 */
export async function loadEnums(): Promise<EnumDictionary> {
  if (cache) return cache;
  if (!inflight) {
    inflight = healthApi
      .enums()
      .then((dict) => {
        cache = { ...FALLBACK_ENUMS, ...dict };
        return cache;
      })
      .catch(() => FALLBACK_ENUMS)
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** React hook：返回枚举字典（初始为内置兜底，拿到后端后替换）。 */
export function useEnums(): EnumDictionary {
  const [dict, setDict] = useState<EnumDictionary>(cache ?? FALLBACK_ENUMS);
  useEffect(() => {
    let alive = true;
    void loadEnums().then((next) => {
      if (alive) setDict(next);
    });
    return () => {
      alive = false;
    };
  }, []);
  return dict;
}
