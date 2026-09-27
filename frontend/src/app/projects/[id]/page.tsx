import type { Metadata } from 'next';
import { ProjectDetailView } from './project-detail-view';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  return { title: `项目 ${id}` };
}

export default async function ProjectDetailPage({ params }: PageProps): Promise<React.ReactElement> {
  const { id } = await params;
  return <ProjectDetailView projectId={id} />;
}
