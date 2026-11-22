export interface Lamp {
  level: 0 | 1 | 2 | 3 | 4;
  color: 'green' | 'yellow' | 'red' | 'purple' | 'black';
  label: string;
  reasons: string[];
  indicators: {
    ai_declared: boolean;
    ai_score: number | null;
    ai_detector_reliable: boolean;
    ai_detected: boolean;
    ai_propagated: { src: string; material: string; declared_src: string; distance: number }[];
    public_person: boolean;
    public_person_strong: boolean;
    manipulation_score: number;
    manipulative: boolean;
  };
}

export interface MaterialRow {
  id: string;
  label: string;
  source: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  error: string | null;
  title: string | null;
  domains: string[];
  persons: string[];
  topic: string | null;
  campaign: string | null;
  lamp: Lamp | null;
  thumbnail: number | null;
  completeness: number | null;
}

export interface Evidence {
  channel: string;
  feature: string;
  value: string;
  weight: number;
  detail: string;
}

export interface PairView {
  a: string;
  b: string;
  score: number;
  relation: 'duplicate' | 'variant' | 'related' | 'unrelated';
  channels: Record<string, number>;
  evidence: Evidence[];
  evidence_total: number;
}

export interface Assignment {
  decision: 'known_campaign' | 'related' | 'new_pattern';
  campaign: string | null;
  family: string | null;
  explanation: string;
  best_score: number;
  neighbours: PairView[];
}

export interface PersonInfo {
  slug: string;
  name: string;
  role: string;
  materials?: number;
}

export interface Transcript {
  src: string;
  language: string | null;
  duration: number | null;
  text: string;
  segments: { start: number; end: number; text: string }[];
}

export interface Features {
  summary: {
    title: string;
    landing_url: string | null;
    landing_domains: string[];
    aux_domains: string[];
    text_chars: number;
    images: number;
    faces: number;
    elapsed_s: number;
  };
  tokens: Record<string, Record<string, number>>;
  text: {
    titles: string[];
    headings: string[];
    body: string;
    ocr: { src: string; text: string }[];
    transcripts?: Transcript[];
    keywords: string[];
  };
  persons: Record<string, string[]>;
  brands: Record<string, number>;
  topics: Record<string, number>;
  manipulation: { score: number; categories: Record<string, string[]>; exclamations: number; caps_ratio: number; method: string };
  narrative_llm?: { narracja?: string; manipulacja?: number; techniki?: string[]; wezwanie_do_dzialania?: string; model?: string };
  ai: { declared: boolean; declarations: { source: string; text: string }[]; image_scores?: { src: string; p: number }[] };
  faces: { src: string; bbox: number[]; score: number; match: { slug: string; sim: number } | null }[];
  images: { src: string; kind: string; w: number; h: number; sha1: string; phash: string }[];
  video: { src: string; duration_s?: number; width?: number; height?: number; error?: string }[];
  infra: {
    hosts: Record<string, number>;
    ips: { ip: string; shared_network: string | null; hosts: string[]; landing: boolean }[];
    redirects: string[][];
    servers: string[];
    rdap: Record<string, Record<string, unknown>>;
  };
  trackers: Record<string, string[]>;
  meta: { ad?: Record<string, string | null>; capture?: Record<string, string | null> };
  completeness: {
    artifacts: Record<string, number>;
    has_network_log: boolean;
    has_page: boolean;
    has_visual: boolean;
    has_video: boolean;
    has_ad_metadata: boolean;
    warnings: string[];
    score: number;
  };
}

export interface MaterialView {
  id: string;
  label: string;
  source: string;
  status: MaterialRow['status'];
  error: string | null;
  input_url: string | null;
  artifacts: { index: number; name: string; kind: string; size: number }[];
  features: Features | null;
  labels: Record<string, string>;
  lamp: Lamp | null;
  assignment: Assignment | null;
}

export interface SignatureItem {
  feature: string;
  channel: string;
  value: string;
  label: string;
  members: number;
  weight: number;
}

export interface Campaign {
  id: string;
  name: string;
  members: string[];
  size: number;
  topic: string;
  persons: PersonInfo[];
  brands: Record<string, number>;
  domains: string[];
  signature: SignatureItem[];
  cohesion: number | null;
  family: string | null;
  max_lamp: Lamp | null;
  titles: Record<string, string | null>;
}

export interface Family {
  id: string;
  campaigns: string[];
  links: { a: string; b: string; score: number }[];
}

export interface GraphData {
  nodes: { id: string; label: string; title: string | null; campaign: string | null; lamp: number; domains: string[] }[];
  edges: { source: string; target: string; score: number; relation: string; top: string[]; channels: Record<string, number> }[];
  thresholds: { campaign: number; family: number };
}

export interface AiDetectorInfo {
  trained: boolean;
  reliable: boolean;
  model: string;
  mode?: 'supervised' | 'pu';
  features?: string;
  positives?: number;
  positive_sources?: number;
  negatives?: number;
  unlabeled?: number;
  heldout_auc?: number | null;
  unlabeled_flag_rate?: number | null;
  reason?: string;
  reliable_requires: { positives: number; positive_sources: number; heldout_auc: number; max_unlabeled_flag_rate: number };
}

export interface SystemStatus {
  materials: number;
  modules: {
    ocr: boolean;
    faces: boolean;
    faces_gallery: Record<string, number>;
    llm: { configured: boolean; reachable: boolean; model: string };
    online_enrichment: boolean;
    asr: { enabled: boolean; installed: boolean; model: string; device: string; loaded: boolean; error: string | null };
    clip: { enabled: boolean; model: string; key: string; present: boolean; error: string | null };
    ai_detector: AiDetectorInfo;
    ai_seed: {
      ai: number;
      real: number;
      ai_sources: number;
      real_sources: number;
      job: { running: boolean; error?: string | null; result?: Record<string, unknown> };
    };
  };
  thresholds: Record<string, number>;
  import: { running: boolean; total?: number; started_at?: number; finished_at?: number };
}

export const TOPIC_PL: Record<string, string> = {
  investment: 'inwestycje / szybki zysk',
  health: 'zdrowie / suplementy',
  celebrity_news_bait: 'fałszywy artykuł o celebrycie',
  gambling: 'hazard / gry',
  giveaway_lottery: 'loteria / nagrody',
  government_benefit: 'dopłaty / świadczenia',
};

export const RELATION_PL: Record<string, string> = {
  duplicate: 'duplikat',
  variant: 'ta sama kampania',
  related: 'podobna kampania',
  unrelated: 'brak powiązania',
};

export const MANIPULATION_PL: Record<string, string> = {
  urgency: 'presja czasu',
  secrecy_conspiracy: 'sekret / spisek',
  unrealistic_gain: 'nierealne zyski',
  miracle_health: 'cudowne leczenie',
  fear_shock: 'strach / szok',
  authority_social_proof: 'autorytet / dowód społeczny',
  official_benefit_bait: 'fałszywy program rządowy / dopłata',
};
