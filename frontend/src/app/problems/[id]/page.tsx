import type { Metadata } from 'next';
import { ProblemDetailView } from './problem-detail-view';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  return { title: `题目 ${id}` };
}

export default async function ProblemDetailPage({ params }: PageProps): Promise<React.ReactElement> {
  const { id } = await params;
  return <ProblemDetailView problemId={id} />;
}
