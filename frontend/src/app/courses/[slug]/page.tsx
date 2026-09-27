import type { Metadata } from 'next';
import { CourseDetailView } from './course-detail-view';

export const dynamic = 'force-dynamic';

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  return { title: `课程 ${slug}` };
}

export default async function CourseDetailPage({ params }: PageProps): Promise<React.ReactElement> {
  const { slug } = await params;
  return <CourseDetailView slug={slug} />;
}
