// ── LinkedIn scraper models (mirror backend Pydantic models) ──

export interface Experience {
  position_title: string | null;
  institution_name: string | null;
  linkedin_url: string | null;
  from_date: string | null;
  to_date: string | null;
  duration: string | null;
  location: string | null;
  description: string | null;
}

export interface Education {
  institution_name: string | null;
  degree: string | null;
  linkedin_url: string | null;
  from_date: string | null;
  to_date: string | null;
  description: string | null;
}

export interface Contact {
  type: string;
  value: string;
  label: string | null;
}

export interface Accomplishment {
  category: string;
  title: string;
  issuer: string | null;
  issued_date: string | null;
  credential_id: string | null;
  credential_url: string | null;
  description: string | null;
}

export interface Interest {
  name: string;
  category: string;
  linkedin_url: string | null;
}

export interface Person {
  linkedin_url: string;
  name: string | null;
  location: string | null;
  about: string | null;
  open_to_work: boolean;
  experiences: Experience[];
  educations: Education[];
  interests: Interest[];
  accomplishments: Accomplishment[];
  contacts: Contact[];
}

export interface CompanySummary {
  linkedin_url: string | null;
  name: string | null;
  followers: string | null;
}

export interface Employee {
  name: string;
  designation: string | null;
  linkedin_url: string | null;
}

export interface Company {
  linkedin_url: string;
  name: string | null;
  about_us: string | null;
  website: string | null;
  phone: string | null;
  headquarters: string | null;
  founded: string | null;
  industry: string | null;
  company_type: string | null;
  company_size: string | null;
  specialties: string | null;
  headcount: number | null;
  showcase_pages: CompanySummary[];
  affiliated_companies: CompanySummary[];
  employees: Employee[];
}

export interface Job {
  linkedin_url: string;
  job_title: string | null;
  company: string | null;
  company_linkedin_url: string | null;
  location: string | null;
  posted_date: string | null;
  applicant_count: string | null;
  job_description: string | null;
  benefits: string | null;
}

export interface Post {
  linkedin_url: string | null;
  urn: string | null;
  text: string | null;
  posted_date: string | null;
  reactions_count: number | null;
  comments_count: number | null;
  reposts_count: number | null;
  image_urls: string[];
  video_url: string | null;
  article_url: string | null;
}

// ── Extract Users types ──

export interface PostEngagementUser {
  name: string;
  headline: string | null;
  profile_url: string | null;
  engagement_type: 'reaction' | 'repost';
}

export interface ExtractUsersResult {
  company_url: string;
  posts_scraped: number;
  users: PostEngagementUser[];
}

// ── API types ──

export interface Session {
  id: string;
  name: string;
  is_active: boolean;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScrapeJob {
  id: string;
  session_id: string;
  scrape_type: string;
  input_url: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress_percent: number;
  progress_message: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ScrapeResult {
  id: string;
  job_id: string;
  scrape_type: string;
  result_data: Person | Company | Job | Post[] | string[];
  created_at: string;
}

export interface HistoryList {
  items: ScrapeJob[];
  total: number;
  page: number;
  per_page: number;
}

export interface AppSettings {
  browser_headless: boolean;
  browser_slow_mo: number;
  max_concurrent_sessions: number;
}

export type ScrapeType = 'person' | 'company' | 'job' | 'job_search' | 'company_posts';
