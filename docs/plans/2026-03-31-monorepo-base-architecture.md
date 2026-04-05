# Monorepo, CI/CD & Base Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish the monorepo directory structure, PostgreSQL-backed Docker Compose dev environment, AWS infrastructure via Terraform (ECS + RDS + S3), a React/Vite frontend scaffold with auth, and an AWS-targeting CI/CD pipeline.

**Architecture:** The existing FastAPI backend lives at the repo root (`src/`, `pyproject.toml`, `Dockerfile`). We keep it in place and scaffold `apps/web/` (React + Vite SPA with auth), `packages/` (shared types), and `infra/terraform/` (AWS ECS, RDS, S3). Docker Compose is extended with a PostgreSQL service. GitHub Actions CI gets a new staging deploy job that builds/pushes to ECR and rolls out to ECS.

**Tech Stack:** FastAPI (Python 3.11), React 18 + Vite + TypeScript, PostgreSQL 16, Redis 7, Docker Compose, Terraform ≥ 1.6, GitHub Actions, AWS ECS (Fargate), AWS RDS, AWS S3, AWS ECR, AWS SSM Parameter Store.

---

## Task 1: Monorepo Directory Scaffold

**Files:**
- Create: `apps/web/.gitkeep` (placeholder until Task 3 creates the React app)
- Create: `packages/README.md`
- Create: `infra/README.md`
- Create: `.env.example`

**Step 1: Create directory structure**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
mkdir -p apps packages infra/terraform
```

**Step 2: Create packages README**

Create `packages/README.md`:

```markdown
# packages/

Shared code used across multiple apps.

- `packages/types/` — Shared TypeScript types (API contracts, form schemas)
- `packages/utils/` — Shared utilities (date formatting, currency helpers)
```

**Step 3: Create infra README**

Create `infra/README.md`:

```markdown
# infra/

Infrastructure-as-Code for the GBO CPA Tax AI Platform.

## Structure
- `infra/terraform/` — AWS resources: ECS, RDS, S3, ECR, VPC

## Prerequisites
- Terraform >= 1.6
- AWS CLI configured with a profile that has permissions to manage ECS, RDS, S3, ECR, VPC, IAM
- An existing AWS account and region set in `infra/terraform/terraform.tfvars`

## Deploy
```bash
cd infra/terraform
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```
```

**Step 4: Create `.env.example`**

Create `.env.example` at the repo root:

```bash
# ============================================================
# App secrets — copy to .env and fill in values
# ============================================================
APP_SECRET_KEY=change-me-32-chars-minimum-xxxxxxxx
JWT_SECRET=change-me-32-chars-minimum-xxxxxxxx
ENCRYPTION_KEY=change-me-32-chars-minimum-xxxxxxxx

# ============================================================
# Database
# ============================================================
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/jorss_gbo
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=jorss_gbo

# ============================================================
# Redis
# ============================================================
REDIS_URL=redis://:changeme@localhost:6379/0
REDIS_PASSWORD=changeme

# ============================================================
# AI Providers (at least one required)
# ============================================================
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

# ============================================================
# AWS (staging/production only — local dev uses Docker)
# ============================================================
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=
AWS_ECR_REGISTRY=

# ============================================================
# Secrets in AWS SSM (production path prefix)
# SSM paths: /jorss-gbo/{env}/{key}
# ============================================================
# APP_SECRET_KEY       → /jorss-gbo/staging/app-secret-key
# JWT_SECRET           → /jorss-gbo/staging/jwt-secret
# ENCRYPTION_KEY       → /jorss-gbo/staging/encryption-key
# DATABASE_URL         → /jorss-gbo/staging/database-url
# OPENAI_API_KEY       → /jorss-gbo/staging/openai-api-key
# ANTHROPIC_API_KEY    → /jorss-gbo/staging/anthropic-api-key
```

**Step 5: Verify structure**

```bash
ls apps/ packages/ infra/terraform/
cat .env.example
```

Expected: directories exist, `.env.example` has all keys.

**Step 6: Commit**

```bash
git add apps/ packages/ infra/ .env.example
git commit -m "feat: scaffold monorepo dirs and .env.example

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 2: Add PostgreSQL to Docker Compose

The existing `docker-compose.yml` uses SQLite (`DATABASE_PATH`). We add a `postgres` service and switch the `app` service to use `DATABASE_URL`.

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Read current docker-compose.yml**

```bash
cat docker-compose.yml
```

**Step 2: Add postgres service and update app environment**

In `docker-compose.yml`, add after the `redis` service:

```yaml
  # ---------------------------------------------------------------------------
  # PostgreSQL Database
  # ---------------------------------------------------------------------------
  postgres:
    image: postgres:16-alpine
    container_name: jorss-gbo-postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER:-postgres}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=${POSTGRES_DB:-jorss_gbo}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - jorss-gbo-net
```

In the `app` service's `environment:` block, add:
```yaml
      - DATABASE_URL=postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@postgres:5432/${POSTGRES_DB:-jorss_gbo}
```

In the `app` service's `depends_on:` block, add:
```yaml
      postgres:
        condition: service_healthy
```

In the `volumes:` block at the bottom, add:
```yaml
  postgres-data:
```

**Step 3: Verify docker-compose syntax**

```bash
docker compose config --quiet && echo "✓ config valid"
```

Expected: `✓ config valid` (no errors).

**Step 4: Smoke test startup**

```bash
docker compose up -d postgres redis
docker compose ps
```

Expected: both `jorss-gbo-postgres` and `jorss-gbo-redis` show `healthy`.

**Step 5: Commit**

```bash
docker compose down -v
git add docker-compose.yml
git commit -m "feat: add PostgreSQL service to Docker Compose

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 3: React + Vite App Scaffold with Auth (`apps/web/`)

Creates a minimal React 18 + Vite + TypeScript app at `apps/web/` with login/logout pages and a protected route. No full backend wiring yet — just the scaffold and auth flow pattern.

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/pages/Login.tsx`
- Create: `apps/web/src/pages/Dashboard.tsx`
- Create: `apps/web/src/context/AuthContext.tsx`
- Create: `apps/web/src/api/auth.ts`
- Create: `apps/web/.env.example`

**Step 1: Create package.json**

Create `apps/web/package.json`:

```json
{
  "name": "@jorss-gbo/web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint src --ext ts,tsx",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.24.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.0",
    "vite": "^5.3.0",
    "vitest": "^1.6.0",
    "@vitest/ui": "^1.6.0",
    "jsdom": "^24.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "eslint": "^9.0.0"
  }
}
```

**Step 2: Create vite.config.ts**

Create `apps/web/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
  },
})
```

**Step 3: Create tsconfig.json**

Create `apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

**Step 4: Create index.html**

Create `apps/web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GBO AI Tax Advisor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 5: Create AuthContext**

Create `apps/web/src/context/AuthContext.tsx`:

```typescript
import { createContext, useContext, useState, ReactNode } from 'react'

interface User {
  id: string
  email: string
  name: string
  role: 'taxpayer' | 'cpa' | 'admin'
}

interface AuthContextValue {
  user: User | null
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem('token')
  )

  async function login(email: string, password: string) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const data = await res.json()
      throw new Error(data.detail ?? 'Login failed')
    }
    const data = await res.json()
    setToken(data.access_token)
    setUser(data.user)
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('user', JSON.stringify(data.user))
  }

  function logout() {
    setUser(null)
    setToken(null)
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return (
    <AuthContext.Provider
      value={{ user, token, login, logout, isAuthenticated: !!user }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
```

**Step 6: Create Login page**

Create `apps/web/src/pages/Login.tsx`:

```typescript
import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '80px auto', padding: 24 }}>
      <h1>GBO AI Tax Advisor</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />
        </div>
        {error && <p role="alert" style={{ color: 'red' }}>{error}</p>}
        <button type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
```

**Step 7: Create Dashboard page**

Create `apps/web/src/pages/Dashboard.tsx`:

```typescript
import { useAuth } from '../context/AuthContext'

export default function Dashboard() {
  const { user, logout } = useAuth()
  return (
    <div style={{ padding: 24 }}>
      <h1>Dashboard</h1>
      <p>Welcome, {user?.name} ({user?.role})</p>
      <button onClick={logout}>Sign out</button>
    </div>
  )
}
```

**Step 8: Create api/auth.ts**

Create `apps/web/src/api/auth.ts`:

```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? ''

export async function apiFetch(
  path: string,
  options: RequestInit = {},
  token?: string | null
): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${API_BASE}${path}`, { ...options, headers })
}
```

**Step 9: Create App.tsx**

Create `apps/web/src/App.tsx`:

```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'

function ProtectedRoute({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
```

**Step 10: Create main.tsx**

Create `apps/web/src/main.tsx`:

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

**Step 11: Create test setup and auth context test**

Create `apps/web/src/test-setup.ts`:

```typescript
import '@testing-library/jest-dom'
```

Create `apps/web/src/__tests__/AuthContext.test.tsx`:

```typescript
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider, useAuth } from '../context/AuthContext'

function TestConsumer() {
  const { isAuthenticated, user, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      {user && <span data-testid="name">{user.name}</span>}
      <button onClick={logout}>logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => localStorage.clear())

  it('starts unauthenticated when localStorage is empty', () => {
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('no')
  })

  it('restores session from localStorage', () => {
    const user = { id: '1', email: 'a@b.com', name: 'Alice', role: 'taxpayer' as const }
    localStorage.setItem('token', 'tok')
    localStorage.setItem('user', JSON.stringify(user))
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    expect(screen.getByTestId('auth')).toHaveTextContent('yes')
    expect(screen.getByTestId('name')).toHaveTextContent('Alice')
  })

  it('clears auth state on logout', async () => {
    const user = { id: '1', email: 'a@b.com', name: 'Alice', role: 'taxpayer' as const }
    localStorage.setItem('token', 'tok')
    localStorage.setItem('user', JSON.stringify(user))
    render(<AuthProvider><TestConsumer /></AuthProvider>)
    await act(async () => userEvent.click(screen.getByText('logout')))
    expect(screen.getByTestId('auth')).toHaveTextContent('no')
    expect(localStorage.getItem('token')).toBeNull()
  })
})
```

**Step 12: Install dependencies and run tests**

```bash
cd apps/web
npm install
npm test
```

Expected: 3 tests pass.

**Step 13: Create apps/web/.env.example**

```bash
# Vite env vars (prefix VITE_ to expose to the browser)
VITE_API_URL=http://localhost:8000
```

**Step 14: Commit**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
git add apps/web/
git commit -m "feat: add React/Vite SPA scaffold with auth context and protected routes

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 4: Terraform AWS Infrastructure (`infra/terraform/`)

Creates the full AWS infrastructure definition: VPC, ECS Fargate cluster, ECR repository, RDS PostgreSQL, S3, ALB, and SSM parameter placeholders.

**Files:**
- Create: `infra/terraform/main.tf`
- Create: `infra/terraform/variables.tf`
- Create: `infra/terraform/outputs.tf`
- Create: `infra/terraform/terraform.tfvars.example`

**Step 1: Create variables.tf**

Create `infra/terraform/variables.tf`:

```hcl
variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
}

variable "app_name" {
  description = "Application name used in resource naming"
  type        = string
  default     = "jorss-gbo"
}

variable "db_username" {
  description = "RDS master username"
  type        = string
  default     = "postgres"
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password (store in SSM, not tfvars)"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "ecs_cpu" {
  description = "ECS task CPU units (256 = 0.25 vCPU)"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "ECS task memory in MiB"
  type        = number
  default     = 1024
}

variable "container_image" {
  description = "Full ECR image URI with tag (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/jorss-gbo:latest)"
  type        = string
}
```

**Step 2: Create main.tf**

Create `infra/terraform/main.tf`:

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Uncomment and configure backend for team use:
  # backend "s3" {
  #   bucket = "jorss-gbo-tf-state"
  #   key    = "infra/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      App         = var.app_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  prefix = "${var.app_name}-${var.environment}"
}

# ===========================================================================
# VPC
# ===========================================================================
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags = { Name = "${local.prefix}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.prefix}-igw" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
  tags = { Name = "${local.prefix}-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
  tags = { Name = "${local.prefix}-public-b" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "${var.aws_region}a"
  tags = { Name = "${local.prefix}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.12.0/24"
  availability_zone = "${var.aws_region}b"
  tags = { Name = "${local.prefix}-private-b" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.prefix}-public-rt" }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# ===========================================================================
# Security Groups
# ===========================================================================
resource "aws_security_group" "alb" {
  name        = "${local.prefix}-alb-sg"
  description = "ALB — allow HTTP/HTTPS from internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs" {
  name        = "${local.prefix}-ecs-sg"
  description = "ECS tasks — allow traffic from ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = "${local.prefix}-rds-sg"
  description = "RDS — allow PostgreSQL from ECS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
}

# ===========================================================================
# ECR
# ===========================================================================
resource "aws_ecr_repository" "app" {
  name                 = "${local.prefix}-app"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ===========================================================================
# ECS Cluster
# ===========================================================================
resource "aws_ecs_cluster" "main" {
  name = "${local.prefix}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.prefix}"
  retention_in_days = 14
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "${local.prefix}-ecs-task-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS to read SSM secrets
resource "aws_iam_role_policy" "ecs_ssm" {
  name = "${local.prefix}-ecs-ssm"
  role = aws_iam_role.ecs_task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["ssm:GetParameters", "ssm:GetParameter"]
      Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/jorss-gbo/${var.environment}/*"
    }]
  })
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${local.prefix}-app"
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name      = "app"
    image     = var.container_image
    essential = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "ENVIRONMENT", value = var.environment },
      { name = "SESSION_STORAGE_TYPE", value = "redis" }
    ]
    secrets = [
      { name = "APP_SECRET_KEY", valueFrom = "/jorss-gbo/${var.environment}/app-secret-key" },
      { name = "JWT_SECRET",     valueFrom = "/jorss-gbo/${var.environment}/jwt-secret" },
      { name = "DATABASE_URL",   valueFrom = "/jorss-gbo/${var.environment}/database-url" },
      { name = "REDIS_URL",      valueFrom = "/jorss-gbo/${var.environment}/redis-url" },
      { name = "ANTHROPIC_API_KEY", valueFrom = "/jorss-gbo/${var.environment}/anthropic-api-key" }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "app"
      }
    }
    healthCheck = {
      command     = ["CMD-SHELL", "curl -sf http://localhost:8000/health/live || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = "${local.prefix}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups = [aws_security_group.ecs.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]
}

# ===========================================================================
# ALB
# ===========================================================================
resource "aws_lb" "main" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_lb_target_group" "app" {
  name        = "${local.prefix}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health/live"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ===========================================================================
# RDS PostgreSQL
# ===========================================================================
resource "aws_db_subnet_group" "main" {
  name       = "${local.prefix}-db-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.prefix}-postgres"
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  storage_type           = "gp3"
  db_name                = "jorss_gbo"
  username               = var.db_username
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = var.environment != "production"
  deletion_protection    = var.environment == "production"
  backup_retention_period = var.environment == "production" ? 7 : 1
}

# ===========================================================================
# S3 (document storage)
# ===========================================================================
resource "aws_s3_bucket" "documents" {
  bucket = "${local.prefix}-documents"
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**Step 3: Create outputs.tf**

Create `infra/terraform/outputs.tf`:

```hcl
output "alb_dns_name" {
  description = "ALB DNS name for the staging environment"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for pushing images"
  value       = aws_ecr_repository.app.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "s3_bucket_name" {
  description = "S3 bucket name for document storage"
  value       = aws_s3_bucket.documents.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.app.name
}
```

**Step 4: Create terraform.tfvars.example**

Create `infra/terraform/terraform.tfvars.example`:

```hcl
aws_region    = "us-east-1"
environment   = "staging"
app_name      = "jorss-gbo"
db_username   = "postgres"
db_password   = "CHANGE-ME-use-ssm-in-production"
container_image = "123456789.dkr.ecr.us-east-1.amazonaws.com/jorss-gbo-staging-app:latest"
```

**Step 5: Validate Terraform syntax**

```bash
cd infra/terraform
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

**Step 6: Commit**

```bash
cd /Users/rakeshanita/jorss-gbo-taai
git add infra/terraform/
git commit -m "feat: add Terraform config for AWS ECS, RDS, S3, ALB

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 5: Update CI/CD Pipeline for AWS ECS Staging Deploy

Extends the existing `.github/workflows/ci.yml` with a staging deploy job that:
1. Builds and pushes the Docker image to ECR
2. Renders a new ECS task definition with the fresh image tag
3. Deploys to ECS (rolling update)

**Files:**
- Modify: `.github/workflows/ci.yml`

**Required GitHub Secrets (add in repo Settings → Secrets → Actions):**
- `AWS_ACCESS_KEY_ID` — IAM key with ECR push + ECS deploy permissions
- `AWS_SECRET_ACCESS_KEY` — corresponding secret
- `AWS_REGION` — e.g. `us-east-1`
- `ECR_REGISTRY` — e.g. `123456789.dkr.ecr.us-east-1.amazonaws.com`
- `ECR_REPOSITORY` — e.g. `jorss-gbo-staging-app`
- `ECS_CLUSTER` — e.g. `jorss-gbo-staging-cluster`
- `ECS_SERVICE` — e.g. `jorss-gbo-staging-app`
- `ECS_TASK_DEFINITION` — task definition family name, e.g. `jorss-gbo-staging-app`
- `CONTAINER_NAME` — `app`

**Step 1: Add deploy-staging job to ci.yml**

Append the following job to `.github/workflows/ci.yml` (after the existing `deploy` job that targets Render):

```yaml
  deploy-staging:
    name: Deploy to AWS ECS Staging
    needs: [backend, frontend]
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image to ECR
        id: build-image
        env:
          ECR_REGISTRY: ${{ secrets.ECR_REGISTRY }}
          ECR_REPOSITORY: ${{ secrets.ECR_REPOSITORY }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Download current ECS task definition
        env:
          ECS_TASK_DEFINITION: ${{ secrets.ECS_TASK_DEFINITION }}
        run: |
          aws ecs describe-task-definition \
            --task-definition $ECS_TASK_DEFINITION \
            --query taskDefinition \
            > task-definition.json

      - name: Render new ECS task definition with updated image
        id: render-task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: ${{ secrets.CONTAINER_NAME }}
          image: ${{ steps.build-image.outputs.image }}

      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.render-task-def.outputs.task-definition }}
          service: ${{ secrets.ECS_SERVICE }}
          cluster: ${{ secrets.ECS_CLUSTER }}
          wait-for-service-stability: true

      - name: ECS staging deploy health check
        env:
          ALB_URL: ${{ secrets.STAGING_ALB_URL }}
        run: |
          if [ -z "$ALB_URL" ]; then
            echo "::notice::STAGING_ALB_URL not set — skipping health check"
            exit 0
          fi
          for i in {1..5}; do
            STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$ALB_URL/health/live") || true
            [ "$STATUS" = "200" ] && echo "Health check passed" && exit 0
            echo "Attempt $i: got $STATUS, retrying in 15s…"
            sleep 15
          done
          echo "::warning::Staging health check timed out after 5 attempts"
```

**Step 2: Verify CI YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "✓ YAML valid"
```

Expected: `✓ YAML valid`

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add AWS ECS staging deploy job to CI pipeline

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Task 6: Shared Types Package (`packages/types/`)

Creates a minimal shared TypeScript types package that the React app (and future Node services) can import. Covers the API auth contract.

**Files:**
- Create: `packages/types/package.json`
- Create: `packages/types/tsconfig.json`
- Create: `packages/types/src/index.ts`
- Create: `packages/types/src/auth.ts`

**Step 1: Create package.json**

Create `packages/types/package.json`:

```json
{
  "name": "@jorss-gbo/types",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts"
  }
}
```

**Step 2: Create auth types**

Create `packages/types/src/auth.ts`:

```typescript
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
```

**Step 3: Create index.ts**

Create `packages/types/src/index.ts`:

```typescript
export * from './auth'
```

**Step 4: Create tsconfig.json**

Create `packages/types/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "declaration": true
  },
  "include": ["src"]
}
```

**Step 5: Commit**

```bash
git add packages/types/
git commit -m "feat: add shared types package for auth API contract

Co-Authored-By: Paperclip <noreply@paperclip.ing>"
```

---

## Verification Checklist

After all tasks complete:

```bash
# Monorepo structure
ls apps/ packages/ infra/terraform/

# Docker Compose is valid and starts postgres+redis
docker compose config --quiet && echo "✓ compose valid"
docker compose up -d postgres redis && docker compose ps

# React app builds
cd apps/web && npm install && npm test && npm run build

# Terraform is valid
cd infra/terraform && terraform init -backend=false && terraform validate

# CI YAML is valid
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "✓ CI valid"
```

Expected: all commands succeed.
