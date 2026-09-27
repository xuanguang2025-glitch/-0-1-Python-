import type { Metadata } from 'next';
import { LessonView } from './lesson-view';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  return { title: `课时 ${id}` };
}

export default async function LessonPage({ params }: PageProps): Promise<React.ReactElement> {
  const { id } = await params;
  return <LessonView lessonId={id} />;
}
