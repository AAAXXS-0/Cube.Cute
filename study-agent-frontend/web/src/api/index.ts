import { HttpStudyApi } from './httpStudyApi';
import { MockStudyApi } from './mockStudyApi';
import type { StudyApi } from './studyApi';

export const apiMode = import.meta.env.VITE_API_MODE === 'http' ? 'http' : 'mock';

export const studyApi: StudyApi = apiMode === 'http'
  ? new HttpStudyApi(import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000/api/v1')
  : new MockStudyApi();

export const mockApi = studyApi instanceof MockStudyApi ? studyApi : null;

export { StudyApiError } from './studyApi';
