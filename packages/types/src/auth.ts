export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  user: UserProfile
}

export interface UserProfile {
  id: string
  email: string
  name: string
  role: 'taxpayer' | 'cpa' | 'admin'
}

export interface ApiError {
  detail: string
  code?: string
}
