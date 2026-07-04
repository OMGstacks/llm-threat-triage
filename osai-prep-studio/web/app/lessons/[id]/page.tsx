import LessonPlayer from "@/components/LessonPlayer";

// Narrated-lesson route, e.g. /lessons/L03. The player consumes the offline-generated
// render manifest served from /public/lessons/<id>.manifest.json.
export default function LessonPage({ params }: { params: { id: string } }) {
  return <LessonPlayer lessonId={params.id} />;
}
