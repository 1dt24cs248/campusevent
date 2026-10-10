import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Layout } from './components/Layout';
import { LoginPage } from './pages/LoginPage';
import { ManagementDashboard } from './features/management/ManagementDashboard';
import { Simulator } from './features/simulator/Simulator';
import { AIAssistant } from './features/user/AIAssistant';
import { NavPanel } from './features/user/NavPanel';
import { NotificationsPage } from './features/user/NotificationsPage';
import { StudentEmergency } from './features/user/StudentEmergency';
import { CampusActionForm } from './features/user/CampusActionForm';
import { MyReports } from './features/user/MyReports';
import { FoodPage } from './features/user/FoodPage';
import { ActionCenter } from './features/management/ActionCenter';
import { StudentManagement } from './features/management/StudentManagement';
import { FacultyManagement } from './features/management/FacultyManagement';
import { FoodManagement } from './features/management/FoodManagement';
import { AcademicManagement } from './features/management/AcademicManagement';
import { ManagementAuditLog } from './features/management/ManagementAuditLog';
import { StudentDashboard } from './features/user/StudentDashboard';
import { StudentProfile } from './features/user/StudentProfile';
import { StudentAcademics, StudentSubjectDetail } from './features/user/StudentAcademics';
import { StudentTimetable } from './features/user/StudentTimetable';
import { FacultyDashboard } from './features/faculty/FacultyDashboard';
import { FacultyProfile } from './features/faculty/FacultyProfile';
import { FacultyAttendance } from './features/faculty/FacultyAttendance';
import { FacultyAcademicManagement } from './features/faculty/FacultyAcademicManagement';
import { FacultyClassroomRequests } from './features/faculty/FacultyClassroomRequests';
import { FacultySubjectRequests as FacultySubjectRequestsFaculty } from './features/faculty/FacultySubjectRequests';
import { FacultySubjectRequests as FacultySubjectRequestsManagement } from './features/management/FacultySubjectRequests';
import { FacultyEvents, FacultySections, FacultySubjects, FacultyTimetable } from './features/faculty/FacultyTeaching';
import { ClassroomRequests } from './features/management/ClassroomRequests';
import { EventDetail, ManagementEvents, StudentEvents } from './features/events/EventPages';

const queryClient = new QueryClient();

const RoleHome: React.FC = () => {
  const { user } = useAuth();
  if (user?.role === 'MANAGEMENT') return <Navigate to="/management" replace />;
  if (user?.role === 'FACULTY') return <Navigate to="/faculty" replace />;
  if (user?.role === 'STUDENT') return <Navigate to="/student" replace />;
  return <Navigate to="/login" replace />;
};

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<ProtectedRoute><RoleHome /></ProtectedRoute>} />
            <Route path="/management" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout>
                  <ManagementDashboard />
                </Layout>
              </ProtectedRoute>
            } />
            <Route path="/simulator" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout>
                  <Simulator />
                </Layout>
              </ProtectedRoute>
            } />
            <Route path="/action-center" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><ActionCenter /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/students" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><StudentManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/faculty" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><FacultyManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/faculty-subject-requests" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><FacultySubjectRequestsManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/academics" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><AcademicManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/audit" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><ManagementAuditLog /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/classroom-requests" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><ClassroomRequests /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/events" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><ManagementEvents /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/management/food" element={
              <ProtectedRoute allowedRoles={['MANAGEMENT']}>
                <Layout><FoodManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/report" element={
              <ProtectedRoute allowedRoles={['STUDENT', 'FACULTY']}>
                <Layout><CampusActionForm /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/reports" element={
              <ProtectedRoute allowedRoles={['STUDENT', 'FACULTY']}>
                <Layout><MyReports /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/food" element={
              <ProtectedRoute><Layout><FoodPage /></Layout></ProtectedRoute>
            } />
            <Route path="/student" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout>
                  <StudentDashboard />
                </Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/profile" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentProfile /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/academics" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentAcademics /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/academics/:subjectId" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentSubjectDetail /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/timetable" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentTimetable /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/emergency" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentEmergency /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/student/events" element={
              <ProtectedRoute allowedRoles={['STUDENT']}>
                <Layout><StudentEvents /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyDashboard /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/profile" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyProfile /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/subjects" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultySubjects /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/subject-requests" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultySubjectRequestsFaculty /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/sections" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultySections /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/timetable" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyTimetable /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/attendance" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyAttendance /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/academics" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyAcademicManagement /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/classroom-requests" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyClassroomRequests /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/faculty/events" element={
              <ProtectedRoute allowedRoles={['FACULTY']}>
                <Layout><FacultyEvents /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/notifications" element={
              <ProtectedRoute><Layout><NotificationsPage /></Layout></ProtectedRoute>
            } />
            <Route path="/events/:eventId" element={
              <ProtectedRoute allowedRoles={['STUDENT', 'FACULTY', 'MANAGEMENT']}>
                <Layout><EventDetail /></Layout>
              </ProtectedRoute>
            } />
            <Route path="/navigator" element={
              <ProtectedRoute><Layout><NavPanel /></Layout></ProtectedRoute>
            } />
            <Route path="/ai" element={
              <ProtectedRoute><Layout><AIAssistant /></Layout></ProtectedRoute>
            } />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
};

export default App;
