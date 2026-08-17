'use client';
import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

export default function TransactionsPage() {
  const router = useRouter();
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <button onClick={() => router.back()} className="flex items-center gap-2 text-sm text-white/40 hover:text-white/70 mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back
      </button>
      <h2 className="text-xl font-semibold text-white mb-2">Transactions</h2>
      <p className="text-sm text-white/40">Full transaction history is available on the Accounts page. <button className="text-violet-400 underline" onClick={() => router.push('/accounts')}>Go to Accounts</button></p>
    </div>
  );
}
