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

// ── API types ──

export interface Session {
  id: string;
  name: string;
  is_active: boolean;
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AppSettings {
  browser_headless: boolean;
  browser_slow_mo: number;
  max_concurrent_sessions: number;
}

// ── Company monitoring types ──

export interface CRMCompany {
  id: string;
  name: string | null;
  linkedinUrl: any; // Can be string or {primaryLinkUrl: string}
  lastPostScrapedAt: string | null;
  [key: string]: any;
}

export interface ScrapeRun {
  id: string;
  companyLinkedinUrl: string;
  companyCrmId: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed';
  phase: string;
  progressPercent: number | null;
  progressMessage: string | null;
  errorMessage: string | null;
  totalPostsFound: number | null;
  postsProcessed: number | null;
  totalUsersFound: number | null;
  newUsersFound: number | null;
  profilesScraped: number | null;
  profilesToScrape: number | null;
  usersSynced: number | null;
  createdAt: string;
  [key: string]: any;
}

export interface CompanyPost {
  id: string;
  urn: string;
  companyLinkedinUrl: string;
  linkedinUrl: string | null;
  postText: string | null;
  postedDate: string | null;
  reactionsCount: number | null;
  commentsCount: number | null;
  repostsCount: number | null;
  lastScrapedAt: string | null;
  [key: string]: any;
}

export interface DiscoveredUser {
  id: string;
  name: any; // {firstName, lastName}
  jobTitle: string | null;
  linkedinUrl: any;
  profileScrapedAt: string | null;
  discoveredFromCompany: string | null;
  [key: string]: any;
}

// Helper to extract LinkedIn URL from Twenty's link field
export function getLinkedInUrl(field: any): string {
  if (!field) return '';
  if (typeof field === 'string') return field;
  return field.primaryLinkUrl || '';
}

// Helper to get display name from Twenty's name field
export function getDisplayName(name: any): string {
  if (!name) return '';
  if (typeof name === 'string') return name;
  return `${name.firstName || ''} ${name.lastName || ''}`.trim();
}
