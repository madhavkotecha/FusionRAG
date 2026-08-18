import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { AuthGuard } from './components/auth/AuthGuard';
import { AdminGuard } from './components/auth/AdminGuard';
import { AppShell } from './components/layout/AppShell';
import { LoginPage } from './pages/LoginPage';
import { OidcCallbackPage } from './pages/OidcCallbackPage';
import { DashboardPage } from './pages/DashboardPage';
import { PipelineEditorPage } from './pages/PipelineEditorPage';
import { PipelineRunsPage } from './pages/PipelineRunsPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { IngestionPipelinesPage } from './pages/IngestionPipelinesPage';
import { IngestionJobsPage } from './pages/IngestionJobsPage';
import { IngestionJobDetailPage } from './pages/IngestionJobDetailPage';
import { DataStoresPage } from './pages/DataStoresPage';
import { NewDataStorePage } from './pages/NewDataStorePage';
import { QueryPipelinesPage } from './pages/QueryPipelinesPage';
import { ChatPage } from './pages/ChatPage';
import { AdminDashboardPage } from './pages/admin/AdminDashboardPage';
import { UserManagementPage } from './pages/admin/UserManagementPage';
import { QueueManagementPage } from './pages/admin/QueueManagementPage';
import { AuditLogPage } from './pages/admin/AuditLogPage';
import { ApiKeysPage } from './pages/admin/ApiKeysPage';
import { SystemSettingsPage } from './pages/admin/SystemSettingsPage';
import { ServiceHealthPage } from './pages/admin/ServiceHealthPage';
import { WorkspaceManagementPage } from './pages/admin/WorkspaceManagementPage';
import { TeamManagementPage } from './pages/admin/TeamManagementPage';
import { ComponentCreatorPage } from './pages/ComponentCreatorPage';
import { AdminComponentsPage } from './pages/AdminComponentsPage';
import { TestCanvasPage } from './pages/TestCanvasPage';
import { PublishPage } from './pages/PublishPage';

function ProtectedPage({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>
        <ErrorBoundary>{children}</ErrorBoundary>
      </AppShell>
    </AuthGuard>
  );
}

function AdminPage({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>
        <ErrorBoundary>
          <AdminGuard>{children}</AdminGuard>
        </ErrorBoundary>
      </AppShell>
    </AuthGuard>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/oidc/callback" element={<OidcCallbackPage />} />
          <Route path="/test-canvas" element={<TestCanvasPage />} />
          <Route path="/" element={<ProtectedPage><DashboardPage /></ProtectedPage>} />
          <Route path="/chat" element={<ProtectedPage><ChatPage /></ProtectedPage>} />
          <Route path="/publish" element={<ProtectedPage><PublishPage /></ProtectedPage>} />
          <Route path="/components" element={<ProtectedPage><ComponentCreatorPage /></ProtectedPage>} />
          <Route path="/query-pipelines" element={<ProtectedPage><QueryPipelinesPage /></ProtectedPage>} />
          <Route path="/query-pipelines/:id/edit" element={<ProtectedPage><PipelineEditorPage /></ProtectedPage>} />
          <Route path="/pipelines/:id/edit" element={<ProtectedPage><PipelineEditorPage /></ProtectedPage>} />
          <Route path="/pipelines/:id/runs" element={<ProtectedPage><PipelineRunsPage /></ProtectedPage>} />
          <Route path="/ingestion/documents" element={<ProtectedPage><DocumentsPage /></ProtectedPage>} />
          <Route path="/ingestion/pipelines" element={<ProtectedPage><IngestionPipelinesPage /></ProtectedPage>} />
          <Route path="/ingestion/jobs" element={<ProtectedPage><IngestionJobsPage /></ProtectedPage>} />
          <Route path="/ingestion/jobs/:id" element={<ProtectedPage><IngestionJobDetailPage /></ProtectedPage>} />
          <Route path="/ingestion/datastores" element={<ProtectedPage><DataStoresPage /></ProtectedPage>} />
          <Route path="/ingestion/datastores/new" element={<ProtectedPage><NewDataStorePage /></ProtectedPage>} />
          <Route path="/knowledge-bases" element={<Navigate to="/ingestion/datastores" replace />} />
          <Route path="/knowledge-bases/:id" element={<Navigate to="/ingestion/datastores" replace />} />
          {/* Admin Routes */}
          <Route path="/admin" element={<AdminPage><AdminDashboardPage /></AdminPage>} />
          <Route path="/admin/users" element={<AdminPage><UserManagementPage /></AdminPage>} />
          <Route path="/admin/queue" element={<AdminPage><QueueManagementPage /></AdminPage>} />
          <Route path="/admin/audit-logs" element={<AdminPage><AuditLogPage /></AdminPage>} />
          <Route path="/admin/api-keys" element={<AdminPage><ApiKeysPage /></AdminPage>} />
          <Route path="/admin/settings" element={<AdminPage><SystemSettingsPage /></AdminPage>} />
          <Route path="/admin/health" element={<AdminPage><ServiceHealthPage /></AdminPage>} />
          <Route path="/admin/teams" element={<AdminPage><TeamManagementPage /></AdminPage>} />
          <Route path="/admin/workspaces" element={<AdminPage><WorkspaceManagementPage /></AdminPage>} />
          <Route path="/admin/components" element={<AdminPage><AdminComponentsPage /></AdminPage>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
