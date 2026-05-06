import { useState } from 'react';
import { Mail, Clock, AlertTriangle, CheckCircle, Copy, Send, Check } from 'lucide-react';
import { ResolutionPackage, ResolutionEmail } from '../types';

interface ResolutionPackageProps {
  data: ResolutionPackage;
}

export function ResolutionPackageComponent({ data }: ResolutionPackageProps) {
  const [sentStatus, setSentStatus] = useState<Record<string, boolean>>({
    carrier: false,
    alternate: false,
    internal: false,
  });
  
  const [copiedStatus, setCopiedStatus] = useState<Record<string, boolean>>({
    carrier: false,
    alternate: false,
    internal: false,
  });

  const handleCopy = (email: ResolutionEmail, key: string) => {
    const content = `To: ${email.to}\nSubject: ${email.subject}\n\n${email.body}`;
    navigator.clipboard.writeText(content);
    setCopiedStatus((prev) => ({ ...prev, [key]: true }));
    setTimeout(() => {
      setCopiedStatus((prev) => ({ ...prev, [key]: false }));
    }, 2000);
  };

  const handleMarkSent = (key: string) => {
    setSentStatus((prev) => ({ ...prev, [key]: true }));
  };

  const handleApproveAll = () => {
    setSentStatus({
      carrier: true,
      alternate: true,
      internal: true,
    });
    
    // Copy all content
    const allContent = `
--- CARRIER EMAIL ---
To: ${data.carrier_email.to}
Subject: ${data.carrier_email.subject}
${data.carrier_email.body}

--- ALTERNATE SUPPLIER EMAIL ---
To: ${data.alternate_supplier_email.to}
Subject: ${data.alternate_supplier_email.subject}
${data.alternate_supplier_email.body}

--- INTERNAL ESCALATION EMAIL ---
To: ${data.internal_escalation_email.to}
Subject: ${data.internal_escalation_email.subject}
${data.internal_escalation_email.body}
`;
    navigator.clipboard.writeText(allContent);
  };

  const allSent = sentStatus.carrier && sentStatus.alternate && sentStatus.internal;

  const renderEmailCard = (title: string, email: ResolutionEmail, stateKey: string) => {
    const isSent = sentStatus[stateKey];
    const isCopied = copiedStatus[stateKey];

    return (
      <div className={`flex-1 rounded-lg border p-4 flex flex-col ${isSent ? 'border-green-500/50 bg-slate-800/80' : 'border-slate-700 bg-slate-800'} shadow-lg transition-colors`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-slate-400" />
            <span className="font-semibold text-slate-200 text-sm">{title}</span>
          </div>
          {isSent && <span className="text-xs font-bold text-green-400 flex items-center gap-1"><CheckCircle className="w-3 h-3" /> SENT</span>}
        </div>
        
        <div className="flex flex-wrap gap-2 mb-3">
          <span className={`text-xs px-2 py-0.5 rounded flex items-center gap-1 ${email.priority === 'urgent' ? 'bg-red-500/20 text-red-400 border border-red-500/30' : 'bg-slate-700 text-slate-300'}`}>
            {email.priority === 'urgent' ? <AlertTriangle className="w-3 h-3" /> : null}
            {email.priority.toUpperCase()}
          </span>
          <span className="text-xs px-2 py-0.5 rounded bg-slate-700 text-slate-300 flex items-center gap-1">
            <Clock className="w-3 h-3" /> Send within {email.send_within_hours}h
          </span>
        </div>

        <div className="text-xs text-slate-400 mb-1">To: <span className="text-slate-300">{email.to}</span></div>
        <div className="text-sm font-bold text-slate-100 mb-3 border-b border-slate-700 pb-2">Subject: {email.subject}</div>
        
        <div className="text-sm text-slate-300 whitespace-pre-wrap flex-1 overflow-y-auto max-h-[200px] mb-4 pr-1">
          {email.body}
        </div>

        <div className="flex gap-2 mt-auto pt-3 border-t border-slate-700">
          <button 
            onClick={() => handleCopy(email, stateKey)}
            className="flex-1 btn-secondary flex items-center justify-center gap-2 text-xs py-1.5"
          >
            {isCopied ? <Check className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
            {isCopied ? 'Copied!' : 'Copy'}
          </button>
          <button 
            onClick={() => handleMarkSent(stateKey)}
            disabled={isSent}
            className={`flex-1 flex items-center justify-center gap-2 text-xs py-1.5 rounded transition-colors ${
              isSent 
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed' 
                : 'bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 border border-indigo-500/30'
            }`}
          >
            <Send className="w-3 h-3" />
            {isSent ? 'Sent' : 'Mark Sent'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="mt-8 mb-4 border border-slate-700 rounded-xl bg-slate-900 overflow-hidden shadow-2xl">
      <div className="bg-slate-800 p-4 border-b border-slate-700 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="animate-pulse">🚨</span> AI Resolution Package Ready
          </h2>
          <p className="text-slate-400 text-sm mt-1">Review and approve actions for {data.shipment_id}</p>
        </div>
        <div className="text-xs text-slate-500">
          Generated: {new Date(data.generated_at).toLocaleString()}
        </div>
      </div>

      <div className="p-6">
        {/* CFO Summary */}
        <div className="mb-8 rounded-lg border border-amber-500/30 bg-amber-500/5 p-5">
          <div className="flex items-center gap-2 mb-4">
            <div className="bg-amber-500 text-slate-900 font-bold px-2 py-0.5 rounded text-xs">CFO SUMMARY</div>
            <div className="text-red-400 font-bold text-sm flex items-center gap-1 ml-auto">
              <Clock className="w-4 h-4" /> Decision Deadline: {data.cfo_summary.decision_deadline}
            </div>
          </div>
          
          <h3 className="text-xl md:text-2xl font-bold text-slate-100 mb-4">
            {data.cfo_summary.headline}
          </h3>
          
          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Key Facts</h4>
              <ul className="space-y-1">
                {data.cfo_summary.key_facts.map((fact, idx) => (
                  <li key={idx} className="text-sm text-slate-300 flex items-start gap-2">
                    <span className="text-amber-500 mt-1">•</span>
                    <span>{fact}</span>
                  </li>
                ))}
              </ul>
            </div>
            
            <div className="flex flex-col justify-center">
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Recommended Action</h4>
                <p className="text-slate-200 font-medium">{data.cfo_summary.recommended_action}</p>
                <div className="mt-3 text-2xl font-bold text-amber-500">
                  ${data.cfo_summary.exposure_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })} <span className="text-sm text-slate-500 font-normal">Exposure</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Email Cards */}
        <h3 className="text-lg font-bold text-slate-200 mb-4">Communication Drafts</h3>
        <div className="grid lg:grid-cols-3 gap-4 mb-8">
          {renderEmailCard('Carrier / Forwarder', data.carrier_email, 'carrier')}
          {renderEmailCard('Alternate Supplier', data.alternate_supplier_email, 'alternate')}
          {renderEmailCard('Internal Escalation', data.internal_escalation_email, 'internal')}
        </div>

        {/* Action Bottom */}
        <div className="flex flex-col items-center justify-center pt-4 border-t border-slate-800">
          <button
            onClick={handleApproveAll}
            disabled={allSent}
            className={`px-8 py-4 rounded-lg font-bold text-lg flex items-center gap-3 transition-all transform hover:scale-105 shadow-lg ${
              allSent 
                ? 'bg-green-600/20 text-green-500 border border-green-500/30 cursor-not-allowed' 
                : 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white hover:from-emerald-500 hover:to-teal-500'
            }`}
          >
            {allSent ? (
              <>
                <CheckCircle className="w-6 h-6" />
                ALL ACTIONS COMPLETED
              </>
            ) : (
              <>
                <span className="text-xl">✅</span>
                APPROVE ALL & MARK SENT
              </>
            )}
          </button>
          
          <p className="text-sm text-slate-400 mt-3">
            {allSent 
              ? 'Emails copied to clipboard for sending' 
              : 'Click to copy all emails and mark actions as complete'}
          </p>
          
          <div className="mt-8 text-xs text-slate-500 flex items-center gap-1.5 opacity-70">
            <AlertTriangle className="w-3 h-3" />
            AI-generated drafts. Review before sending. All communications remain your responsibility.
          </div>
        </div>
      </div>
    </div>
  );
}
