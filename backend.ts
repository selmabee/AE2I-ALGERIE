const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'Admin' | 'Recruteur' | 'Lecteur';
}

interface LoginResponse {
  token: string;
  user: User;
}

interface Candidate {
  id: string;
  full_name: string;
  email: string;
  phone?: string;
  position?: string;
  linkedin_url?: string;
  linkedin_data?: Record<string, unknown>;
  cv_url?: string;
  pdf_summary_url?: string;
  skills?: string[];
  status: 'nouveau' | 'en_cours' | 'accepte' | 'refuse';
  created_at: string;
  updated_at: string;
}

interface MediaFile {
  id: string;
  file_name: string;
  file_type: 'image' | 'video' | 'pdf' | 'cv';
  file_url: string;
  file_size: number;
  uploaded_at: string;
  metadata?: Record<string, unknown>;
}

interface LinkedInAuthResponse {
  auth_url: string;
  state: string;
}

interface LinkedInProfile {
  sub: string;
  name: string;
  given_name: string;
  family_name: string;
  email: string;
  picture?: string;
}

class BackendAPI {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  private getHeaders(includeAuth = true): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (includeAuth && this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    return headers;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...options,
        headers: {
          ...this.getHeaders(),
          ...options.headers,
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.error || 'Une erreur est survenue',
        };
      }

      return {
        success: true,
        data,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Erreur réseau',
      };
    }
  }

  async register(
    email: string,
    password: string,
    full_name: string,
    role: 'Admin' | 'Recruteur' | 'Lecteur' = 'Lecteur'
  ): Promise<ApiResponse<{ user: User }>> {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, full_name, role }),
    });
  }

  async login(email: string, password: string): Promise<ApiResponse<LoginResponse>> {
    const response = await this.request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (response.success && response.data) {
      this.setToken(response.data.token);
    }

    return response;
  }

  logout() {
    this.clearToken();
  }

  async getCandidates(): Promise<ApiResponse<{ candidates: Candidate[] }>> {
    return this.request('/candidates', { method: 'GET' });
  }

  async createCandidate(candidateData: Partial<Candidate>): Promise<ApiResponse<{ candidate: Candidate }>> {
    return this.request('/candidates', {
      method: 'POST',
      body: JSON.stringify(candidateData),
    });
  }

  async updateCandidate(
    candidateId: string,
    updates: Partial<Candidate>
  ): Promise<ApiResponse<{ candidate: Candidate }>> {
    return this.request(`/candidates/${candidateId}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteCandidate(candidateId: string): Promise<ApiResponse<void>> {
    return this.request(`/candidates/${candidateId}`, {
      method: 'DELETE',
    });
  }

  async uploadFile(file: File, fileType: string): Promise<ApiResponse<{ file: MediaFile }>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('file_type', fileType);

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.error || 'Erreur lors du téléversement',
        };
      }

      return {
        success: true,
        data,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Erreur réseau',
      };
    }
  }

  getDownloadUrl(filename: string): string {
    return `${API_BASE_URL}/download/${filename}`;
  }

  getCvDownloadUrl(candidateId: string): string {
    return `${API_BASE_URL}/cv/${candidateId}`;
  }

  getPdfSummaryDownloadUrl(candidateId: string): string {
    return `${API_BASE_URL}/pdf_summary/${candidateId}`;
  }

  async downloadFile(url: string): Promise<void> {
    window.open(url, '_blank');
  }

  async getMediaFiles(type?: string): Promise<ApiResponse<{ files: MediaFile[] }>> {
    const query = type ? `?type=${type}` : '';
    return this.request(`/media${query}`, { method: 'GET' });
  }

  async getLinkedInAuthUrl(): Promise<ApiResponse<LinkedInAuthResponse>> {
    return this.request('/linkedin_auth', { method: 'GET' });
  }

  async saveLinkedInProfile(
    accessToken: string,
    refreshToken?: string
  ): Promise<ApiResponse<void>> {
    return this.request('/linkedin_profile', {
      method: 'POST',
      body: JSON.stringify({ access_token: accessToken, refresh_token: refreshToken }),
    });
  }

  async getSettings(): Promise<ApiResponse<{ settings: Record<string, unknown> }>> {
    return this.request('/settings', { method: 'GET' });
  }

  async updateSettings(settings: Record<string, unknown>): Promise<ApiResponse<void>> {
    return this.request('/settings', {
      method: 'POST',
      body: JSON.stringify(settings),
    });
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  async initiateLinkedInAuth(): Promise<void> {
    const response = await this.getLinkedInAuthUrl();

    if (response.success && response.data) {
      localStorage.setItem('linkedin_state', response.data.state);
      window.location.href = response.data.auth_url;
    } else {
      throw new Error(response.error || 'Impossible d\'initier l\'authentification LinkedIn');
    }
  }

  async handleLinkedInCallback(code: string, state: string): Promise<LinkedInProfile | null> {
    const savedState = localStorage.getItem('linkedin_state');

    if (state !== savedState) {
      throw new Error('État LinkedIn invalide');
    }

    const response = await fetch(`${API_BASE_URL}/linkedin_callback?code=${code}&state=${state}`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || 'Erreur lors de la récupération du profil LinkedIn');
    }

    if (data.access_token) {
      await this.saveLinkedInProfile(data.access_token);
    }

    localStorage.removeItem('linkedin_state');

    return data.profile;
  }
}

export const backendAPI = new BackendAPI();

export type {
  User,
  Candidate,
  MediaFile,
  LinkedInProfile,
  ApiResponse,
};
