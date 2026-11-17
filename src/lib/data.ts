import modelsJson from '../data/generated/models.json';
import docsJson from '../data/generated/docs.json';
import archiveJson from '../data/generated/archive.json';
import { MODEL_NOTES, MODEL_FEATURES } from '../data/content';

export type Photo = { src: string; thumb: string; w: number; h: number; alt: string; caption?: string };
export type Era = { key: string; title: string; from: number; to: number };
export type Model = {
  slug: string; name: string; type: string | null; category: string; month: number | null;
  year: number; approx: boolean; launchDoc: string | null; price: number | null;
  extra?: boolean; curiosity?: boolean; note?: string; order: number; era: Era; series: string | null;
  photos: Photo[]; brochures: { title: string; pages: Photo[] }[]; docs: string[]; features?: string[];
};
export type Doc = {
  id: string; title: string; kind: 'user' | 'service' | 'schematic' | 'leaflet' | 'drawing' | 'catalogue' | 'book';
  models: string[]; note: string; pages: number; size: number;
  cover: { src: string; w: number; h: number } | null;
};

export const models = (modelsJson as Model[]).map((m) => ({ ...m, note: MODEL_NOTES[m.slug] ?? m.note, features: MODEL_FEATURES[m.slug] ?? [] }));
export const docs = docsJson as Doc[];
export const archive = archiveJson as unknown as {
  book: Photo[]; brochures: { title: string; pages: Photo[] }[];
  press: { title: string; kind: string; pages: Photo[] }[];
  history: Photo[]; production: Photo[]; djs: Photo[]; eras: Era[];
};

export const bySlug = new Map(models.map((m) => [m.slug, m]));
export const docById = new Map(docs.map((d) => [d.id, d]));
export const eras = archive.eras;

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export const yearLabel = (m: Model) => (m.approx ? `c. ${m.year}` : `${m.year}`);
export const dateLabel = (m: Model) => (m.month && !m.approx ? `${MONTHS[m.month - 1]} ${m.year}` : yearLabel(m));
export const priceLabel = (p: number | null) =>
  p == null ? '—' : `€ ${p.toLocaleString('nl-BE', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
export const sizeLabel = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.round(b / 1e3)} kB`);
export const KIND_LABEL: Record<Doc['kind'], string> = {
  user: 'User manual', service: 'Service manual', schematic: 'Schematic', leaflet: 'Leaflet', drawing: 'Drawing', catalogue: 'Catalogue', book: 'Book',
};
export const docUrl = (d: Doc) => `/docs/rodec-${d.id}.pdf`;
export const coverPhoto = (m: Model): Photo | undefined => m.photos[0] ?? m.brochures[0]?.pages[0];
