'use client';
import { useAuth } from '@/components/providers/AuthProvider';

export default function ProfilePage() {
  const { user } = useAuth();
  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      <h2 className="text-xl font-semibold text-white">Profile</h2>
      <div className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
        <p className="text-sm text-white/60">User ID: <span className="font-mono text-white">{user?.userId}</span></p>
        <p className="text-sm text-white/60 mt-1">Role: <span className="text-violet-400 capitalize">{user?.role}</span></p>
      </div>
    </div>
  );
}
