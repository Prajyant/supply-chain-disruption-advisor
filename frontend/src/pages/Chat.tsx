import { useState, useRef, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import { chatApi } from '../services/api';
import { Send, Bot, User, Sparkles, ChevronRight } from 'lucide-react';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  recommendations?: string[];
}

const QUICK_QUESTIONS = [
  'What are the critical risks right now?',
  'Which suppliers are most affected?',
  'What mitigation actions should we take?',
  'Summarize supply chain health',
  'What is machine learning?',
  'Write a Python function to sort a list',
];

export function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const chatMutation = useMutation({
    mutationFn: (question: string) =>
      chatApi.chat(question).then(r => r.data),
    onSuccess: (data, question) => {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: question },
        { role: 'assistant', content: data.answer, recommendations: data.recommendations },
      ]);
    },
    onError: (_err, question) => {
      setMessages(prev => [
        ...prev,
        { role: 'user', content: question },
        { role: 'assistant', content: 'Sorry, something went wrong. Please try again.' },
      ]);
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatMutation.isPending]);

  const handleSend = () => {
    const q = input.trim();
    if (!q || chatMutation.isPending) return;
    chatMutation.mutate(q);
    setInput('');
    inputRef.current?.focus();
  };

  const handleQuick = (q: string) => {
    if (chatMutation.isPending) return;
    chatMutation.mutate(q);
    setInput('');
    inputRef.current?.focus();
  };

  return (
    <div className="h-full flex flex-col bg-slate-950">

      {/* ── Header ── */}
      <div className="px-8 pt-8 pb-5 border-b border-slate-800 shrink-0">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="page-title flex items-center gap-2">
              <Sparkles className="w-6 h-6 text-primary-400" />
              AI Advisor
            </h1>
            <p className="page-subtitle">
              Ask me anything — supply chain insights, general knowledge, coding help, and more
            </p>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="btn-ghost text-xs text-slate-500"
            >
              Clear chat
            </button>
          )}
        </div>

        {/* Quick questions */}
        {messages.length === 0 && (
          <div className="mt-5">
            <p className="text-xs text-slate-500 uppercase tracking-wide font-semibold mb-3">Quick Questions</p>
            <div className="flex flex-wrap gap-2">
              {QUICK_QUESTIONS.map(q => (
                <button
                  key={q}
                  onClick={() => handleQuick(q)}
                  disabled={chatMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 border border-slate-700 hover:border-slate-600 text-slate-300 rounded-lg text-sm transition-all duration-150 disabled:opacity-40"
                >
                  <ChevronRight className="w-3 h-3 text-primary-400 shrink-0" />
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Messages ── */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-5">

        {messages.length === 0 && (
          <div className="empty-state mt-8">
            <div className="w-16 h-16 rounded-2xl bg-primary-600/10 border border-primary-600/20 flex items-center justify-center mb-2">
              <Bot className="w-8 h-8 text-primary-400" />
            </div>
            <p className="empty-state-title">Start a conversation</p>
            <p className="empty-state-body">
              Ask about your shipments and risks, or anything else — I have full supply chain context
              and can answer general questions too.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>

            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-xl bg-primary-600/15 border border-primary-600/25 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4 text-primary-400" />
              </div>
            )}

            <div className={`max-w-2xl rounded-2xl px-4 py-3 ${
              msg.role === 'user'
                ? 'bg-primary-600 text-white rounded-br-sm'
                : 'bg-slate-900 border border-slate-800 text-slate-100 rounded-bl-sm'
            }`}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

              {msg.recommendations && msg.recommendations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700/60">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wide mb-2">
                    Recommendations
                  </p>
                  <ul className="space-y-1.5">
                    {msg.recommendations.map((rec, j) => (
                      <li key={j} className="flex items-start gap-2 text-xs text-slate-300">
                        <span className="text-primary-400 mt-0.5 shrink-0">•</span>
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-xl bg-slate-700 border border-slate-600 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-slate-300" />
              </div>
            )}
          </div>
        ))}

        {/* Thinking indicator */}
        {chatMutation.isPending && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-xl bg-primary-600/15 border border-primary-600/25 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-primary-400" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 bg-primary-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Input ── */}
      <div className="px-8 py-5 border-t border-slate-800 shrink-0">
        {messages.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {['What are the critical risks?', 'Show all shipments', 'What is Docker?'].map(q => (
              <button
                key={q}
                onClick={() => handleQuick(q)}
                disabled={chatMutation.isPending}
                className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 rounded-lg transition-all duration-150 disabled:opacity-40"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
            placeholder="Ask me anything — supply chain, general knowledge, coding…"
            className="input flex-1"
            disabled={chatMutation.isPending}
            autoFocus
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || chatMutation.isPending}
            className="btn-primary flex items-center gap-2 px-5 disabled:opacity-40"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
        <p className="text-[11px] text-slate-700 mt-2 text-center">
          Powered by Groq · qwen/qwen3.8-27b · Full supply chain context loaded
        </p>
      </div>
    </div>
  );
}
